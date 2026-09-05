from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "venue_latitude IS NULL OR (venue_latitude >= -90 AND venue_latitude <= 90)",
            name="ck_courses_venue_latitude",
        ),
        CheckConstraint(
            "venue_longitude IS NULL OR (venue_longitude >= -180 AND venue_longitude <= 180)",
            name="ck_courses_venue_longitude",
        ),
        CheckConstraint(
            "(venue_latitude IS NULL) = (venue_longitude IS NULL)",
            name="ck_courses_venue_coordinates_paired",
        ),
        CheckConstraint("geofence_radius_meters > 0", name="ck_courses_geofence_radius"),
        CheckConstraint("risk_threshold >= 0 AND risk_threshold <= 1", name="ck_courses_risk_threshold"),
        Index("ix_courses_semester", "semester"),
        Index("ix_courses_is_active", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    venue_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    venue_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    geofence_radius_meters: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    require_face_recognition: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_device_binding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    risk_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
