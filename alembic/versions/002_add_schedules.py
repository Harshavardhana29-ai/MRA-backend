"""add scheduled_jobs and job_history tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-25

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
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),

        sa.Column("schedule_type", sa.String(20), nullable=False, server_default="recurring"),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("one_time_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(60), nullable=False, server_default="UTC"),

        sa.Column("wake_mode", sa.String(30), nullable=False, server_default="next-heartbeat"),
        sa.Column("output_format", sa.String(30), nullable=False, server_default="markdown"),
        sa.Column("output_schema", sa.Text(), nullable=True),
        sa.Column("delivery_methods", postgresql.ARRAY(sa.String(30)), nullable=False, server_default="{}"),

        sa.Column("concurrency_policy", sa.String(20), nullable=False, server_default="skip"),
        sa.Column("retry_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retry_max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("retry_delay_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("retry_backoff", sa.String(20), nullable=False, server_default="fixed"),
        sa.Column("auto_disable_after", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(20), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_done", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_sj_workflow_id", "scheduled_jobs", ["workflow_id"])
    op.create_index("idx_sj_status", "scheduled_jobs", ["status"])
    op.create_index("idx_sj_enabled", "scheduled_jobs", ["enabled"])
    op.create_index("idx_sj_next_run", "scheduled_jobs", ["next_run_at"])

    op.create_table(
        "job_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scheduled_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scheduled_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("report_markdown", sa.Text(), nullable=True),
    )
    op.create_index("idx_jh_job_id", "job_history", ["scheduled_job_id"])
    op.create_index("idx_jh_run_date", "job_history", ["run_date"])
    op.create_index("idx_jh_status", "job_history", ["status"])


def downgrade() -> None:
    op.drop_table("job_history")
    op.drop_table("scheduled_jobs")
