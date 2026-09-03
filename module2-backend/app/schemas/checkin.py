from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.checkin import CheckInStatus
from app.models.risk_signal import RiskSeverity, RiskSignalType
from app.models.session import SessionType


class CheckInCreate(BaseModel):
    session_id: str = Field(min_length=1, max_length=36)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_accuracy_meters: float | None = Field(default=None, ge=0, le=10_000)
    device_fingerprint: str = Field(min_length=8, max_length=64)
    liveness_challenge_response: str | None = Field(
        default=None,
        min_length=1,
        max_length=15_000_000,
    )
    qr_code: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("device_fingerprint")
    @classmethod
    def normalize_fingerprint(cls, value: str) -> str:
        value = value.strip()
        if any(character.isspace() for character in value):
            raise ValueError("Device fingerprint cannot contain whitespace")
        return value


class RiskFactorResponse(BaseModel):
    type: RiskSignalType
    severity: RiskSeverity
    weight: float
    confidence: float = 1.0
    details: dict[str, Any] | None = None


class CheckInResponse(BaseModel):
    id: str
    session_id: str
    student_id: str
    status: CheckInStatus
    checked_in_at: datetime
    latitude: float | None
    longitude: float | None
    location_accuracy_meters: float | None
    distance_from_venue_meters: float | None
    liveness_passed: bool | None
    liveness_score: float | None
    face_match_passed: bool | None
    face_match_score: float | None
    risk_score: float
    risk_factors: list[RiskFactorResponse]


class CheckInDetailResponse(CheckInResponse):
    device_id: str | None
    device_trusted: bool | None
    verified_at: datetime | None
    reviewed_by_id: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    appeal_reason: str | None
    appealed_at: datetime | None


class SessionCheckInResponse(BaseModel):
    id: str
    student_id: str
    student_name: str
    student_email: str
    status: CheckInStatus
    checked_in_at: datetime
    distance_from_venue_meters: float | None
    risk_score: float
    risk_factors: list[RiskFactorResponse]
    liveness_passed: bool | None
    device_trusted: bool | None


class CheckInListItemResponse(BaseModel):
    id: str
    session_id: str
    session_name: str
    student_id: str
    student_name: str
    student_email: str
    status: CheckInStatus
    checked_in_at: datetime
    distance_from_venue_meters: float | None
    risk_score: float
    liveness_passed: bool | None


class PaginatedCheckIns(BaseModel):
    items: list[CheckInListItemResponse]
    total: int
    limit: int
    offset: int


class MyCheckInResponse(BaseModel):
    id: str
    session_id: str
    session_name: str
    session_type: SessionType
    course_code: str
    course_name: str
    status: CheckInStatus
    checked_in_at: datetime
    risk_score: float
