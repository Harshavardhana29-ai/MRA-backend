import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sso_id = Column(String(255), unique=True, nullable=False, comment="Unique SSO identifier")
    email = Column(String(320), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    avatar_url = Column(Text, nullable=True)
    role = Column(String(20), nullable=False, server_default="user")
    is_active = Column(Boolean, nullable=False, server_default="true")
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_sso_id", "sso_id"),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, comment="SHA-256 hash of JWT token")
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_session_user_id", "user_id"),
        Index("idx_session_token_hash", "token_hash"),
        Index("idx_session_expires_at", "expires_at"),
    )
