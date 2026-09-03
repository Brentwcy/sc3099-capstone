import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow


class SessionStatus(str, enum.Enum):
    scheduled = "scheduled"
    active = "active"
    closed = "closed"
    cancelled = "cancelled"


class SessionType(str, enum.Enum):
    lecture = "lecture"
    tutorial = "tutorial"
    lab = "lab"
    exam = "exam"


class AttendanceSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("scheduled_end > scheduled_start", name="ck_sessions_scheduled_window"),
        CheckConstraint("checkin_closes_at > checkin_opens_at", name="ck_sessions_checkin_window"),
        CheckConstraint(
            "venue_latitude IS NULL OR (venue_latitude >= -90 AND venue_latitude <= 90)",
            name="ck_sessions_venue_latitude",
        ),
        CheckConstraint(
            "venue_longitude IS NULL OR (venue_longitude >= -180 AND venue_longitude <= 180)",
            name="ck_sessions_venue_longitude",
        ),
        CheckConstraint(
            "(venue_latitude IS NULL) = (venue_longitude IS NULL)",
            name="ck_sessions_venue_coordinates_paired",
        ),
        CheckConstraint(
            "geofence_radius_meters IS NULL OR geofence_radius_meters > 0",
            name="ck_sessions_geofence_radius",
        ),
        CheckConstraint(
            "risk_threshold IS NULL OR (risk_threshold >= 0 AND risk_threshold <= 1)",
            name="ck_sessions_risk_threshold",
        ),
        Index("ix_sessions_course_id", "course_id"),
        Index("ix_sessions_instructor_id", "instructor_id"),
        Index("ix_sessions_status", "status"),
        Index("ix_sessions_scheduled_start", "scheduled_start"),
        Index("ix_sessions_checkin_window", "checkin_opens_at", "checkin_closes_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    instructor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    session_type: Mapped[SessionType] = mapped_column(
        Enum(SessionType, name="session_type", native_enum=False, validate_strings=True),
        nullable=False,
        default=SessionType.lecture,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checkin_opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checkin_closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status", native_enum=False, validate_strings=True),
        nullable=False,
        default=SessionStatus.scheduled,
    )
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    venue_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    geofence_radius_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    require_liveness_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_face_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    qr_code_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qr_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
