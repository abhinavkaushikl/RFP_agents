"""Existing solutions: a per-user library, plus a role on users."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_existing_solutions"
down_revision = "0005_email_otp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=20), nullable=False, server_default="member"))
    op.create_table(
        "existing_solutions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=80)),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("url", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "name", name="uq_existing_solutions_owner_name"),
    )
    op.create_index("ix_existing_solutions_owner_id", "existing_solutions", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_existing_solutions_owner_id", table_name="existing_solutions")
    op.drop_table("existing_solutions")
    op.drop_column("users", "role")
