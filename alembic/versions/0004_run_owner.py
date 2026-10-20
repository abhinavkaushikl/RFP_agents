"""Record who owns each run, so users only see their own work."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_run_owner"
down_revision = "0003_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("workflow_runs", "llm_usage_events"):
        op.add_column(table, sa.Column("owner_id", sa.UUID(), nullable=True))
        op.create_foreign_key(f"fk_{table}_owner_id", table, "users", ["owner_id"], ["id"], ondelete="SET NULL")
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])


def downgrade() -> None:
    for table in ("llm_usage_events", "workflow_runs"):
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_constraint(f"fk_{table}_owner_id", table, type_="foreignkey")
        op.drop_column(table, "owner_id")
