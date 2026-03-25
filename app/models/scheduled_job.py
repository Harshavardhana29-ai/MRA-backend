import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, Boolean,
    ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_prompt = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)

    schedule_type = Column(String(20), nullable=False, default="recurring")
    cron_expression = Column(String(100), nullable=True)
    one_time_date = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String(60), nullable=False, default="UTC")

    wake_mode = Column(String(30), nullable=False, default="next-heartbeat")
    output_format = Column(String(30), nullable=False, default="markdown")
    output_schema = Column(Text, nullable=True)
    delivery_methods = Column(ARRAY(String(30)), nullable=False, default=list)

    concurrency_policy = Column(String(20), nullable=False, default="skip")
    retry_enabled = Column(Boolean, nullable=False, default=False)
    retry_max_attempts = Column(Integer, nullable=False, default=3)
    retry_delay_seconds = Column(Integer, nullable=False, default=60)
    retry_backoff = Column(String(20), nullable=False, default="fixed")
    auto_disable_after = Column(Integer, nullable=False, default=0)

    status = Column(String(20), nullable=False, default="active")
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_status = Column(String(20), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    jobs_done = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    workflow = relationship("Workflow", backref="scheduled_jobs")
    history_entries = relationship(
        "JobHistory", back_populates="scheduled_job",
        cascade="all, delete-orphan", order_by="JobHistory.run_date.desc()",
    )

    __table_args__ = (
        Index("idx_sj_workflow_id", "workflow_id"),
        Index("idx_sj_status", "status"),
        Index("idx_sj_enabled", "enabled"),
        Index("idx_sj_next_run", "next_run_at"),
    )


class JobHistory(Base):
    __tablename__ = "job_history"

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
    run_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(20), nullable=False, default="running")
    duration_seconds = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    report_markdown = Column(Text, nullable=True)

    scheduled_job = relationship("ScheduledJob", back_populates="history_entries")
    workflow_run = relationship("WorkflowRun")

    __table_args__ = (
        Index("idx_jh_job_id", "scheduled_job_id"),
        Index("idx_jh_run_date", "run_date"),
        Index("idx_jh_status", "status"),
    )
