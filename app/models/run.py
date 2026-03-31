import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    user_prompt = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="idle")  # idle, running, completed, failed
    progress = Column(Float, nullable=False, default=0.0)
    report_markdown = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    workflow = relationship("Workflow", back_populates="runs")
    logs = relationship("RunLog", back_populates="run", cascade="all, delete-orphan", order_by="RunLog.timestamp")

    __table_args__ = (
        Index("idx_run_workflow_id", "workflow_id"),
        Index("idx_run_status", "status"),
        Index("idx_run_user_id", "user_id"),
    )


class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    elapsed_time = Column(String(10), nullable=False, default="00:00")
    message = Column(Text, nullable=False)
    log_type = Column(String(20), nullable=False, default="info")  # info, success, error, warning
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    run = relationship("WorkflowRun", back_populates="logs")

    __table_args__ = (
        Index("idx_run_log_run_id_timestamp", "run_id", "timestamp"),
    )
