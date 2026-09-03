"""Create courses, enrollments, and sessions.

Revision ID: 20260821_0003
Revises: 20260821_0002
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260821_0003"
down_revision = "20260821_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("semester", sa.String(length=20), nullable=False),
        sa.Column("instructor_id", sa.String(length=36), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("venue_latitude", sa.Float(), nullable=True),
        sa.Column("venue_longitude", sa.Float(), nullable=True),
        sa.Column("venue_name", sa.String(length=255), nullable=True),
        sa.Column("geofence_radius_meters", sa.Float(), server_default="100.0", nullable=False),
        sa.Column("require_face_recognition", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("require_device_binding", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("risk_threshold", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "venue_latitude IS NULL OR (venue_latitude >= -90 AND venue_latitude <= 90)",
            name="ck_courses_venue_latitude",
        ),
        sa.CheckConstraint(
            "venue_longitude IS NULL OR (venue_longitude >= -180 AND venue_longitude <= 180)",
            name="ck_courses_venue_longitude",
        ),
        sa.CheckConstraint(
            "(venue_latitude IS NULL) = (venue_longitude IS NULL)",
            name="ck_courses_venue_coordinates_paired",
        ),
        sa.CheckConstraint("geofence_radius_meters > 0", name="ck_courses_geofence_radius"),
        sa.CheckConstraint(
            "risk_threshold >= 0 AND risk_threshold <= 1", name="ck_courses_risk_threshold"
        ),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_courses_semester", "courses", ["semester"], unique=False)
    op.create_index("ix_courses_is_active", "courses", ["is_active"], unique=False)
    op.create_index("ix_courses_instructor_id", "courses", ["instructor_id"], unique=False)

    op.create_table(
        "enrollments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dropped_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "course_id", name="uq_enrollments_student_course"),
    )
    op.create_index("ix_enrollments_student_id", "enrollments", ["student_id"], unique=False)
    op.create_index("ix_enrollments_course_id", "enrollments", ["course_id"], unique=False)
    op.create_index(
        "ix_enrollments_course_active", "enrollments", ["course_id", "is_active"], unique=False
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("instructor_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "session_type",
            sa.Enum(
                "lecture", "tutorial", "lab", "exam", name="session_type", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkin_opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkin_closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled", "active", "closed", "cancelled", name="session_status", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("venue_latitude", sa.Float(), nullable=True),
        sa.Column("venue_longitude", sa.Float(), nullable=True),
        sa.Column("venue_name", sa.String(length=255), nullable=True),
        sa.Column("geofence_radius_meters", sa.Float(), nullable=True),
        sa.Column("require_liveness_check", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("require_face_match", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("risk_threshold", sa.Float(), nullable=True),
        sa.Column("qr_code_secret", sa.String(length=64), nullable=True),
        sa.Column("qr_code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("scheduled_end > scheduled_start", name="ck_sessions_scheduled_window"),
        sa.CheckConstraint(
            "checkin_closes_at > checkin_opens_at", name="ck_sessions_checkin_window"
        ),
        sa.CheckConstraint(
            "venue_latitude IS NULL OR (venue_latitude >= -90 AND venue_latitude <= 90)",
            name="ck_sessions_venue_latitude",
        ),
        sa.CheckConstraint(
            "venue_longitude IS NULL OR (venue_longitude >= -180 AND venue_longitude <= 180)",
            name="ck_sessions_venue_longitude",
        ),
        sa.CheckConstraint(
            "(venue_latitude IS NULL) = (venue_longitude IS NULL)",
            name="ck_sessions_venue_coordinates_paired",
        ),
        sa.CheckConstraint(
            "geofence_radius_meters IS NULL OR geofence_radius_meters > 0",
            name="ck_sessions_geofence_radius",
        ),
        sa.CheckConstraint(
            "risk_threshold IS NULL OR (risk_threshold >= 0 AND risk_threshold <= 1)",
            name="ck_sessions_risk_threshold",
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_course_id", "sessions", ["course_id"], unique=False)
    op.create_index("ix_sessions_instructor_id", "sessions", ["instructor_id"], unique=False)
    op.create_index("ix_sessions_status", "sessions", ["status"], unique=False)
    op.create_index("ix_sessions_scheduled_start", "sessions", ["scheduled_start"], unique=False)
    op.create_index(
        "ix_sessions_checkin_window",
        "sessions",
        ["checkin_opens_at", "checkin_closes_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_checkin_window", table_name="sessions")
    op.drop_index("ix_sessions_scheduled_start", table_name="sessions")
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_instructor_id", table_name="sessions")
    op.drop_index("ix_sessions_course_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_enrollments_course_active", table_name="enrollments")
    op.drop_index("ix_enrollments_course_id", table_name="enrollments")
    op.drop_index("ix_enrollments_student_id", table_name="enrollments")
    op.drop_table("enrollments")
    op.drop_index("ix_courses_instructor_id", table_name="courses")
    op.drop_index("ix_courses_is_active", table_name="courses")
    op.drop_index("ix_courses_semester", table_name="courses")
    op.drop_table("courses")
