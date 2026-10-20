"""Email confirmation: a verified-at stamp on users and a table of one-time codes."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_email_otp"
down_revision = "0004_run_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    # Accounts that existed before confirmation was required keep working.
    op.execute("UPDATE users SET email_verified_at = now() WHERE email_verified_at IS NULL")
    op.create_table(
        "email_otps",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_otps_user_id", "email_otps", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_email_otps_user_id", table_name="email_otps")
    op.drop_table("email_otps")
    op.drop_column("users", "email_verified_at")
