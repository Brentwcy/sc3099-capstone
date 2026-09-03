import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow


class DevicePlatform(str, enum.Enum):
    ios = "ios"
    android = "android"
    web = "web"
    desktop = "desktop"


class DeviceTrustScore(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint("total_checkins >= 0", name="ck_devices_total_checkins"),
        Index("ix_devices_user_id", "user_id"),
        Index("ix_devices_is_active", "is_active"),
        Index("ix_devices_is_trusted", "is_trusted"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[DevicePlatform | None] = mapped_column(
        Enum(DevicePlatform, name="device_platform", native_enum=False, validate_strings=True),
        nullable=True,
    )
    browser: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_key_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    public_key_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attestation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_attestation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attestation_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trust_score: Mapped[DeviceTrustScore] = mapped_column(
        Enum(DeviceTrustScore, name="device_trust_score", native_enum=False, validate_strings=True),
        nullable=False,
        default=DeviceTrustScore.low,
    )
    is_emulator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_rooted_jailbroken: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    total_checkins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
