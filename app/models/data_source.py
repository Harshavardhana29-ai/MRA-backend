import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    url = Column(Text, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    topic = Column(String(100), nullable=False, index=True)
    tags = Column(ARRAY(String(100)), nullable=False, default=list)
    status = Column(String(20), nullable=False, default="Active")  # Active, Processing, Error
    is_public = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="raise")
    workflow_associations = relationship(
        "WorkflowDataSource", back_populates="data_source", passive_deletes=True
    )

    __table_args__ = (
        Index("idx_data_source_topic", "topic"),
        Index("idx_data_source_status", "status"),
        Index("idx_data_source_deleted_at", "deleted_at"),
        Index("idx_data_source_title", "title"),
        Index("idx_data_source_user_id", "user_id"),
        Index("idx_data_source_is_public", "is_public"),
    )
