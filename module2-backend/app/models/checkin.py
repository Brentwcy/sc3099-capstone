import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow


class CheckInStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    flagged = "flagged"
    rejected = "rejected"
    appealed = "appealed"


class CheckIn(Base):
    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "student_id", name="uq_checkins_session_student"
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_checkins_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_checkins_longitude",
        ),
        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 1",
            name="ck_checkins_risk_score",
        ),
        Index("ix_checkins_session_id", "session_id"),
        Index("ix_checkins_student_id", "student_id"),
        Index("ix_checkins_status", "status"),
        Index("ix_checkins_checked_in_at", "checked_in_at"),
        Index("ix_checkins_risk_score", "risk_score"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[CheckInStatus] = mapped_column(
        Enum(
            CheckInStatus,
            name="checkin_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default=CheckInStatus.pending,
    )
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_from_venue_meters: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    liveness_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_challenge_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    face_match_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    face_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_embedding_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_code_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reviewed_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    appeal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    appealed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_deletion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
