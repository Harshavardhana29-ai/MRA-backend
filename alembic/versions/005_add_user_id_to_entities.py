"""add user_id to all entity tables

Revision ID: 005
Revises: 004
Create Date: 2026-03-31

Adds user_id FK to data_sources, workflows, workflow_runs,
scheduled_jobs, and activity_logs so every entity is user-scoped.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- data_sources ---
    op.add_column(
        "data_sources",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_data_sources_user_id", "data_sources", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("idx_data_source_user_id", "data_sources", ["user_id"])

    # --- workflows ---
    op.add_column(
        "workflows",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflows_user_id", "workflows", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("idx_workflow_user_id", "workflows", ["user_id"])

    # --- workflow_runs ---
    op.add_column(
        "workflow_runs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_runs_user_id", "workflow_runs", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("idx_run_user_id", "workflow_runs", ["user_id"])

    # --- scheduled_jobs ---
    op.add_column(
        "scheduled_jobs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_scheduled_jobs_user_id", "scheduled_jobs", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("idx_sj_user_id", "scheduled_jobs", ["user_id"])

    # --- activity_logs ---
    op.add_column(
        "activity_logs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_activity_logs_user_id", "activity_logs", "users",
        ["user_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_activity_log_user_id", "activity_logs", ["user_id"])


def downgrade() -> None:
    # --- activity_logs ---
    op.drop_index("idx_activity_log_user_id")
    op.drop_constraint("fk_activity_logs_user_id", "activity_logs", type_="foreignkey")
    op.drop_column("activity_logs", "user_id")

    # --- scheduled_jobs ---
    op.drop_index("idx_sj_user_id")
    op.drop_constraint("fk_scheduled_jobs_user_id", "scheduled_jobs", type_="foreignkey")
    op.drop_column("scheduled_jobs", "user_id")

    # --- workflow_runs ---
    op.drop_index("idx_run_user_id")
    op.drop_constraint("fk_workflow_runs_user_id", "workflow_runs", type_="foreignkey")
    op.drop_column("workflow_runs", "user_id")

    # --- workflows ---
    op.drop_index("idx_workflow_user_id")
    op.drop_constraint("fk_workflows_user_id", "workflows", type_="foreignkey")
    op.drop_column("workflows", "user_id")

    # --- data_sources ---
    op.drop_index("idx_data_source_user_id")
    op.drop_constraint("fk_data_sources_user_id", "data_sources", type_="foreignkey")
    op.drop_column("data_sources", "user_id")
