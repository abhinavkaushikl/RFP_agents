"""Authenticator-app two-step sign-in."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_totp"
down_revision = "0006_existing_solutions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret_enc", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("totp_last_step", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("mfa_backup_hashes", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("users", sa.Column("mfa_failures", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("mfa_locked_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in ("mfa_locked_until", "mfa_failures", "mfa_backup_hashes", "totp_last_step", "totp_enabled_at", "totp_secret_enc"):
        op.drop_column("users", column)
