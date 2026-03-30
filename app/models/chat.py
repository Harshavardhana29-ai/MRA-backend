import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, ForeignKey, Index, Integer, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ChatSession(Base):
    """A conversation session owned by a user. Contains ordered messages."""
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(500), nullable=False, default="New Research")
    is_archived = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    __table_args__ = (
        Index("idx_chat_session_user_id", "user_id"),
        Index("idx_chat_session_updated", "updated_at"),
    )


class ChatMessage(Base):
    """A single message within a chat session (user prompt or assistant response)."""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(20), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    message_type = Column(String(30), nullable=False, default="text")  # 'text' | 'report' | 'error'

    # Link to workflow run (optional — set when a workflow produces this message)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True)
    workflow_title = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("idx_chat_message_session_id", "session_id"),
        Index("idx_chat_message_created", "created_at"),
    )
