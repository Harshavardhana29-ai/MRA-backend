import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    title = Column(String(500), nullable=False)
    topic = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="Draft")  # Active, Draft
    source_selection_mode = Column(String(20), nullable=False, default="topic")  # topic, both, individual, prompt_only
    selected_topics = Column(ARRAY(String(100)), nullable=False, default=list)
    is_public = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="raise")
    data_source_associations = relationship(
        "WorkflowDataSource", back_populates="workflow", cascade="all, delete-orphan"
    )
    agent_associations = relationship(
        "WorkflowAgent", back_populates="workflow", cascade="all, delete-orphan"
    )
    runs = relationship("WorkflowRun", back_populates="workflow", passive_deletes=True)

    __table_args__ = (
        Index("idx_workflow_topic", "topic"),
        Index("idx_workflow_status", "status"),
        Index("idx_workflow_deleted_at", "deleted_at"),
        Index("idx_workflow_user_id", "user_id"),
        Index("idx_workflow_is_public", "is_public"),
    )


class WorkflowDataSource(Base):
    __tablename__ = "workflow_data_sources"

    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        primary_key=True,
    )
    data_source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        primary_key=True,
    )

    workflow = relationship("Workflow", back_populates="data_source_associations")
    data_source = relationship("DataSource", back_populates="workflow_associations")


class WorkflowAgent(Base):
    __tablename__ = "workflow_agents"

    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        primary_key=True,
    )
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )

    workflow = relationship("Workflow", back_populates="agent_associations")
    agent = relationship("Agent", back_populates="workflow_associations")
