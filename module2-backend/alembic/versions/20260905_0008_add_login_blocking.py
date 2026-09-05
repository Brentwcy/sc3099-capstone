"""Add persistent consecutive login failure blocking.

Revision ID: 20260905_0008
Revises: 20260904_0007
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260905_0008"
down_revision = "20260904_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "failed_login_attempts",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("login_blocked_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("login_blocked_at")
        batch_op.drop_column("failed_login_attempts")
