"""Remove non-existent instructor ownership fields.

Revision ID: 20260904_0007
Revises: 20260827_0006
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0007"
down_revision = "20260827_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index("ix_sessions_instructor_id")
        batch_op.drop_column("instructor_id")

    with op.batch_alter_table("courses") as batch_op:
        batch_op.drop_index("ix_courses_instructor_id")
        batch_op.drop_column("instructor_id")


def downgrade() -> None:
    with op.batch_alter_table("courses") as batch_op:
        batch_op.add_column(sa.Column("instructor_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_courses_instructor_id_users",
            "users",
            ["instructor_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_courses_instructor_id", ["instructor_id"], unique=False)

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("instructor_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_sessions_instructor_id_users",
            "users",
            ["instructor_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_sessions_instructor_id", ["instructor_id"], unique=False)
