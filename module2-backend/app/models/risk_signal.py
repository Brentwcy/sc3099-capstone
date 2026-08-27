import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow


class RiskSignalType(str, enum.Enum):
    geo_out_of_bounds = "geo_out_of_bounds"
    impossible_travel = "impossible_travel"
    geo_accuracy_low = "geo_accuracy_low"
    vpn_detected = "vpn_detected"
    proxy_detected = "proxy_detected"
    tor_detected = "tor_detected"
    suspicious_ip = "suspicious_ip"
    device_unknown = "device_unknown"
    device_emulator = "device_emulator"
    device_rooted = "device_rooted"
    attestation_failed = "attestation_failed"
    rapid_succession = "rapid_succession"
    unusual_time = "unusual_time"
    pattern_anomaly = "pattern_anomaly"
    liveness_failed = "liveness_failed"
    liveness_low_confidence = "liveness_low_confidence"
    deepfake_suspected = "deepfake_suspected"
    replay_suspected = "replay_suspected"
    face_match_failed = "face_match_failed"
    face_match_low_confidence = "face_match_low_confidence"


class RiskSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskSignal(Base):
    __tablename__ = "risk_signals"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_risk_signals_confidence",
        ),
        CheckConstraint(
            "weight >= 0 AND weight <= 1",
            name="ck_risk_signals_weight",
        ),
        Index("ix_risk_signals_checkin_id", "checkin_id"),
        Index("ix_risk_signals_signal_type", "signal_type"),
        Index("ix_risk_signals_severity", "severity"),
        Index("ix_risk_signals_detected_at", "detected_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    checkin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("checkins.id", ondelete="CASCADE"), nullable=False
    )
    signal_type: Mapped[RiskSignalType] = mapped_column(
        Enum(
            RiskSignalType,
            name="risk_signal_type",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    severity: Mapped[RiskSeverity] = mapped_column(
        Enum(
            RiskSeverity,
            name="risk_severity",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
