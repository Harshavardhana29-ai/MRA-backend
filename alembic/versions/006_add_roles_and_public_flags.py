"""add roles, admin_id to users and is_public to data_sources/workflows

Revision ID: 006
Revises: 005
Create Date: 2026-04-03

Adds admin_id self-FK on users (assistant → admin relationship),
and is_public boolean flag on data_sources and workflows.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: admin_id (self-referential FK for assistant → admin) ---
    op.add_column(
        "users",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_admin_id", "users", "users",
        ["admin_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_user_admin_id", "users", ["admin_id"])
    op.create_index("idx_user_role", "users", ["role"])

    # --- data_sources: is_public ---
    op.add_column(
        "data_sources",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("idx_data_source_is_public", "data_sources", ["is_public"])

    # --- workflows: is_public ---
    op.add_column(
        "workflows",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("idx_workflow_is_public", "workflows", ["is_public"])


def downgrade() -> None:
    op.drop_index("idx_workflow_is_public")
    op.drop_column("workflows", "is_public")

    op.drop_index("idx_data_source_is_public")
    op.drop_column("data_sources", "is_public")

    op.drop_index("idx_user_role")
    op.drop_index("idx_user_admin_id")
    op.drop_constraint("fk_users_admin_id", "users", type_="foreignkey")
    op.drop_column("users", "admin_id")
