"""Create the check-ins table.

Revision ID: 20260825_0005
Revises: 20260821_0004
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_0005"
down_revision = "20260821_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkins",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "flagged",
                "rejected",
                "appealed",
                name="checkin_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("location_accuracy_meters", sa.Float(), nullable=True),
        sa.Column("distance_from_venue_meters", sa.Float(), nullable=True),
        sa.Column("liveness_passed", sa.Boolean(), nullable=True),
        sa.Column("liveness_score", sa.Float(), nullable=True),
        sa.Column("liveness_challenge_type", sa.String(length=50), nullable=True),
        sa.Column("face_match_passed", sa.Boolean(), nullable=True),
        sa.Column("face_match_score", sa.Float(), nullable=True),
        sa.Column("face_embedding_hash", sa.String(length=64), nullable=True),
        sa.Column("risk_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("risk_factors", sa.Text(), nullable=True),
        sa.Column(
            "qr_code_verified", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("reviewed_by_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("appeal_reason", sa.Text(), nullable=True),
        sa.Column("appealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_deletion_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_checkins_latitude",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_checkins_longitude",
        ),
        sa.CheckConstraint(
            "risk_score >= 0 AND risk_score <= 1",
            name="ck_checkins_risk_score",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "student_id", name="uq_checkins_session_student"
        ),
    )
    op.create_index("ix_checkins_session_id", "checkins", ["session_id"], unique=False)
    op.create_index("ix_checkins_student_id", "checkins", ["student_id"], unique=False)
    op.create_index("ix_checkins_status", "checkins", ["status"], unique=False)
    op.create_index(
        "ix_checkins_checked_in_at", "checkins", ["checked_in_at"], unique=False
    )
    op.create_index("ix_checkins_risk_score", "checkins", ["risk_score"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_checkins_risk_score", table_name="checkins")
    op.drop_index("ix_checkins_checked_in_at", table_name="checkins")
    op.drop_index("ix_checkins_status", table_name="checkins")
    op.drop_index("ix_checkins_student_id", table_name="checkins")
    op.drop_index("ix_checkins_session_id", table_name="checkins")
    op.drop_table("checkins")
