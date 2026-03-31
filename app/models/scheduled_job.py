import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    job_name = Column(String(500), nullable=False)
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_prompt = Column(Text, nullable=True, default="")
    enabled = Column(Boolean, nullable=False, default=True)
    schedule_type = Column(String(20), nullable=False, default="recurring")
    cron_expression = Column(String(100), nullable=True)
    one_time_date = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String(50), nullable=False, default="UTC")
    wake_mode = Column(String(20), nullable=False, default="next-heartbeat")
    output_format = Column(String(20), nullable=False, default="markdown")
    output_schema_text = Column(Text, nullable=True)
    delivery_methods = Column(ARRAY(String(30)), nullable=False, server_default="{internal-log}")
    concurrency_policy = Column(String(10), nullable=False, default="skip")
    retry_enabled = Column(Boolean, nullable=False, default=False)
    retry_max_attempts = Column(Integer, nullable=False, default=3)
    retry_delay_seconds = Column(Integer, nullable=False, default=60)
    retry_backoff = Column(String(20), nullable=False, default="fixed")
    auto_disable_after = Column(Integer, nullable=False, default=0)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active")
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    jobs_done = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    workflow = relationship("Workflow", lazy="raise")
    runs = relationship(
        "ScheduledJobRun", back_populates="scheduled_job",
        cascade="all, delete-orphan", order_by="ScheduledJobRun.started_at.desc()",
    )

    __table_args__ = (
        Index("idx_sj_workflow_id", "workflow_id"),
        Index("idx_sj_status", "status"),
        Index("idx_sj_enabled", "enabled"),
        Index("idx_sj_next_run", "next_run_at"),
        Index("idx_sj_user_id", "user_id"),
    )


class ScheduledJobRun(Base):
    __tablename__ = "scheduled_job_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheduled_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(20), nullable=False, default="running")
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scheduled_job = relationship("ScheduledJob", back_populates="runs")
    workflow_run = relationship("WorkflowRun", lazy="raise")

    __table_args__ = (
        Index("idx_sjr_job_id", "scheduled_job_id"),
        Index("idx_sjr_status", "status"),
    )
