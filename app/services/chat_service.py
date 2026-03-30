"""
Service layer for chat session and message management.
All queries are scoped to the authenticated user for data isolation.
"""
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func, delete, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatSession, ChatMessage
from app.models.user import User
from app.schemas.chat import (
    ChatSessionResponse,
    ChatSessionDetailResponse,
    ChatMessageResponse,
)


async def list_sessions(
    db: AsyncSession,
    user: User,
    *,
    include_archived: bool = False,
) -> list[ChatSessionResponse]:
    """Return all chat sessions for a user, ordered by most recently updated."""
    query = (
        select(
            ChatSession,
            func.count(ChatMessage.id).label("message_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
    )

    if not include_archived:
        query = query.where(ChatSession.is_archived == False)  # noqa: E712

    # Only return sessions that have at least one message (hide empty drafts)
    query = query.having(func.count(ChatMessage.id) > 0)

    result = await db.execute(query)
    rows = result.all()

    sessions: list[ChatSessionResponse] = []
    for row in rows:
        session = row[0]
        msg_count = row[1]

        # Fetch last message preview
        last_msg_q = await db.execute(
            select(ChatMessage.content)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        last_msg = last_msg_q.scalar_one_or_none()
        preview = last_msg[:120] + "…" if last_msg and len(last_msg) > 120 else last_msg

        sessions.append(
            ChatSessionResponse(
                id=session.id,
                title=session.title,
                is_archived=session.is_archived,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=msg_count,
                last_message_preview=preview,
            )
        )

    return sessions


async def get_session(
    db: AsyncSession,
    user: User,
    session_id: UUID,
) -> ChatSessionDetailResponse | None:
    """Get a single chat session with all its messages."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    return ChatSessionDetailResponse(
        id=session.id,
        title=session.title,
        is_archived=session.is_archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            ChatMessageResponse(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                message_type=m.message_type,
                workflow_id=m.workflow_id,
                run_id=m.run_id,
                workflow_title=m.workflow_title,
                created_at=m.created_at,
            )
            for m in session.messages
        ],
    )


async def create_session(
    db: AsyncSession,
    user: User,
    title: str = "New Research",
) -> ChatSessionResponse:
    """Create a new empty chat session."""
    session = ChatSession(
        user_id=user.id,
        title=title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        is_archived=session.is_archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
        last_message_preview=None,
    )


async def rename_session(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    new_title: str,
) -> ChatSessionResponse | None:
    """Rename a chat session. Returns None if not found or not owned."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    session.title = new_title
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    msg_count_q = await db.execute(
        select(func.count()).where(ChatMessage.session_id == session.id).select_from(ChatMessage)
    )
    msg_count = msg_count_q.scalar() or 0

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        is_archived=session.is_archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=msg_count,
        last_message_preview=None,
    )


async def delete_session(
    db: AsyncSession,
    user: User,
    session_id: UUID,
) -> bool:
    """Hard-delete a chat session and all its messages (CASCADE)."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return False

    await db.delete(session)
    await db.commit()
    return True


async def add_message(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    role: str,
    content: str,
    message_type: str = "text",
    workflow_id: UUID | None = None,
    run_id: UUID | None = None,
    workflow_title: str | None = None,
) -> ChatMessageResponse | None:
    """
    Append a message to a chat session.
    Verifies the session belongs to the user.
    Also touches `updated_at` on the session.
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        message_type=message_type,
        workflow_id=workflow_id,
        run_id=run_id,
        workflow_title=workflow_title,
    )
    db.add(msg)

    # Touch session timestamp
    session.updated_at = datetime.now(timezone.utc)

    # Auto-title: if session still has the default title and this is the first user message,
    # set the title from the content
    if role == "user" and session.title == "New Research":
        session.title = content[:80] + ("…" if len(content) > 80 else "")

    await db.commit()
    await db.refresh(msg)

    return ChatMessageResponse(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        message_type=msg.message_type,
        workflow_id=msg.workflow_id,
        run_id=msg.run_id,
        workflow_title=msg.workflow_title,
        created_at=msg.created_at,
    )
