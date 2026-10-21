"""Sign in with Google: remember Google's id for each linked account."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_google_sub"
down_revision = "0007_totp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=64), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
