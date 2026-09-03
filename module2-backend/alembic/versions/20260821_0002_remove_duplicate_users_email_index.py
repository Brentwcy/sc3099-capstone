"""Remove the redundant users email index.

Revision ID: 20260821_0002
Revises: 20260820_0001
Create Date: 2026-08-21
"""

from alembic import op


revision = "20260821_0002"
down_revision = "20260820_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL already creates an index for the users.email UNIQUE
    # constraint, so the explicit unique index duplicates it.
    op.drop_index("ix_users_email", table_name="users")


def downgrade() -> None:
    op.create_index("ix_users_email", "users", ["email"], unique=True)
