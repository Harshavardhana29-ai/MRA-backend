"""add scheduled_jobs and scheduled_job_runs tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-26

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_name", sa.String(500), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=True, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("schedule_type", sa.String(20), nullable=False, server_default="recurring"),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("one_time_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("wake_mode", sa.String(20), nullable=False, server_default="next-heartbeat"),
        sa.Column("output_format", sa.String(20), nullable=False, server_default="markdown"),
        sa.Column("output_schema_text", sa.Text(), nullable=True),
        sa.Column("delivery_methods", postgresql.ARRAY(sa.String(30)), nullable=False, server_default="{internal-log}"),
        sa.Column("concurrency_policy", sa.String(10), nullable=False, server_default="skip"),
        sa.Column("retry_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retry_max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("retry_delay_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("retry_backoff", sa.String(20), nullable=False, server_default="fixed"),
        sa.Column("auto_disable_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("jobs_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_sj_workflow_id", "scheduled_jobs", ["workflow_id"])
    op.create_index("idx_sj_status", "scheduled_jobs", ["status"])
    op.create_index("idx_sj_enabled", "scheduled_jobs", ["enabled"])
    op.create_index("idx_sj_next_run", "scheduled_jobs", ["next_run_at"])

    op.create_table(
        "scheduled_job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scheduled_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scheduled_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_sjr_job_id", "scheduled_job_runs", ["scheduled_job_id"])
    op.create_index("idx_sjr_status", "scheduled_job_runs", ["status"])


def downgrade() -> None:
    op.drop_table("scheduled_job_runs")
    op.drop_table("scheduled_jobs")
