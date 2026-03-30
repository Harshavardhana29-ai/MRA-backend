"""
Chat session & message endpoints.
All endpoints require authentication and scope data to the current user.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionResponse,
    ChatSessionDetailResponse,
    ChatMessageResponse,
    SendMessageRequest,
)
from app.services import chat_service

router = APIRouter()


# ─── Sessions ────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    include_archived: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all chat sessions for the authenticated user."""
    return await chat_service.list_sessions(db, user, include_archived=include_archived)


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(
    body: ChatSessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new empty chat session."""
    return await chat_service.create_session(db, user, title=body.title)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a chat session with all its messages."""
    session = await chat_service.get_session(db, user, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def rename_session(
    session_id: UUID,
    body: ChatSessionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename a chat session."""
    result = await chat_service.rename_session(db, user, session_id, body.title)
    if not result:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return result


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat session and all its messages."""
    deleted = await chat_service.delete_session(db, user, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat session not found")


# ─── Messages ────────────────────────────────────────────────────

@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=201,
)
async def send_message(
    session_id: UUID,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a user message to a chat session.
    If workflow_id is provided, a workflow run is also started.
    The assistant response (report) is added when the run completes.
    """
    # Resolve workflow title if workflow_id is provided
    workflow_title: str | None = None
    if body.workflow_id:
        from sqlalchemy import select
        from app.models.workflow import Workflow
        wf_q = await db.execute(
            select(Workflow.title).where(Workflow.id == UUID(body.workflow_id))
        )
        workflow_title = wf_q.scalar_one_or_none()

    # Save the user message
    user_msg = await chat_service.add_message(
        db, user, session_id,
        role="user",
        content=body.content,
        message_type="text",
        workflow_id=UUID(body.workflow_id) if body.workflow_id else None,
        workflow_title=workflow_title,
    )
    if not user_msg:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # If a workflow is requested, start a run
    if body.workflow_id:
        from app.services import run_service
        try:
            run_result = await run_service.start_run(
                db,
                UUID(body.workflow_id),
                body.content,
                chat_session_id=session_id,
                chat_user=user,
            )
            # Store run_id on the user message
            user_msg.run_id = run_result.run_id
        except ValueError as e:
            # Workflow not found — store error as assistant message
            await chat_service.add_message(
                db, user, session_id,
                role="assistant",
                content=f"Failed to start workflow: {str(e)}",
                message_type="error",
            )

    return user_msg
