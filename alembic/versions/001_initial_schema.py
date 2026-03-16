"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- data_sources ---
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(100)), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_data_source_topic", "data_sources", ["topic"])
    op.create_index("idx_data_source_status", "data_sources", ["status"])
    op.create_index("idx_data_source_deleted_at", "data_sources", ["deleted_at"])
    op.create_index("idx_data_source_title", "data_sources", ["title"])

    # --- agents ---
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("api_url", sa.Text(), nullable=True),
        sa.Column("api_method", sa.String(10), nullable=False, server_default="POST"),
        sa.Column("is_active", sa.String(10), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_agent_name", "agents", ["name"])

    # --- agent_topic_mappings ---
    op.create_table(
        "agent_topic_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
    )
    op.create_index("idx_agent_topic_mapping_topic", "agent_topic_mappings", ["topic"])
    op.create_index("idx_agent_topic_mapping_unique", "agent_topic_mappings", ["agent_id", "topic"], unique=True)

    # --- workflows ---
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("source_selection_mode", sa.String(20), nullable=False, server_default="topic"),
        sa.Column("selected_topics", postgresql.ARRAY(sa.String(100)), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_workflow_topic", "workflows", ["topic"])
    op.create_index("idx_workflow_status", "workflows", ["status"])
    op.create_index("idx_workflow_deleted_at", "workflows", ["deleted_at"])

    # --- workflow_data_sources ---
    op.create_table(
        "workflow_data_sources",
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True),
    )

    # --- workflow_agents ---
    op.create_table(
        "workflow_agents",
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    )

    # --- activity_logs ---
    op.create_table(
        "activity_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_name", sa.String(500), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_activity_log_timestamp", "activity_logs", ["timestamp"])

    # --- workflow_runs ---
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="idle"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("report_markdown", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_run_workflow_id", "workflow_runs", ["workflow_id"])
    op.create_index("idx_run_status", "workflow_runs", ["status"])

    # --- run_logs ---
    op.create_table(
        "run_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("elapsed_time", sa.String(10), nullable=False, server_default="00:00"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("log_type", sa.String(20), nullable=False, server_default="info"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_run_log_run_id_timestamp", "run_logs", ["run_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("run_logs")
    op.drop_table("workflow_runs")
    op.drop_table("activity_logs")
    op.drop_table("workflow_agents")
    op.drop_table("workflow_data_sources")
    op.drop_table("agent_topic_mappings")
    op.drop_table("workflows")
    op.drop_table("agents")
    op.drop_table("data_sources")
