from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.session import SessionStatus, SessionType


class SessionCreate(BaseModel):
    course_id: str
    name: str = Field(min_length=1, max_length=255)
    session_type: SessionType = SessionType.lecture
    description: str | None = Field(default=None, max_length=5000)
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: datetime | None = None
    checkin_closes_at: datetime | None = None
    venue_latitude: float | None = Field(default=None, ge=-90, le=90)
    venue_longitude: float | None = Field(default=None, ge=-180, le=180)
    venue_name: str | None = Field(default=None, max_length=255)
    geofence_radius_meters: float | None = Field(default=None, gt=0, le=10_000)
    require_liveness_check: bool = True
    require_face_match: bool = False
    risk_threshold: float | None = Field(default=None, ge=0, le=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value or "<" in value or ">" in value:
            raise ValueError("Name must be non-blank plain text")
        return value

    @model_validator(mode="after")
    def validate_windows_and_coordinates(self):
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("Scheduled end must be after scheduled start")
        if (self.venue_latitude is None) != (self.venue_longitude is None):
            raise ValueError("Venue latitude and longitude must be provided together")
        if (
            self.checkin_opens_at is not None
            and self.checkin_closes_at is not None
            and self.checkin_closes_at <= self.checkin_opens_at
        ):
            raise ValueError("Check-in close must be after check-in open")
        return self


class SessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    session_type: SessionType | None = None
    description: str | None = Field(default=None, max_length=5000)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    checkin_opens_at: datetime | None = None
    checkin_closes_at: datetime | None = None
    status: SessionStatus | None = None
    venue_latitude: float | None = Field(default=None, ge=-90, le=90)
    venue_longitude: float | None = Field(default=None, ge=-180, le=180)
    venue_name: str | None = Field(default=None, max_length=255)
    geofence_radius_meters: float | None = Field(default=None, gt=0, le=10_000)
    require_liveness_check: bool | None = None
    require_face_match: bool | None = None
    risk_threshold: float | None = Field(default=None, ge=0, le=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or "<" in value or ">" in value:
            raise ValueError("Name must be non-blank plain text")
        return value


class SessionResponse(BaseModel):
    id: str
    course_id: str
    course_code: str | None = None
    course_name: str | None = None
    name: str
    session_type: SessionType
    description: str | None
    status: SessionStatus
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: datetime
    checkin_closes_at: datetime
    actual_start: datetime | None
    actual_end: datetime | None
    venue_latitude: float | None
    venue_longitude: float | None
    venue_name: str | None
    geofence_radius_meters: float | None
    require_liveness_check: bool
    require_face_match: bool
    risk_threshold: float | None
    qr_code_enabled: bool = False
    total_enrolled: int | None = None
    checked_in_count: int | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedSessions(BaseModel):
    items: list[SessionResponse]
    total: int
    limit: int
    offset: int


class AdminSessionStatusUpdate(BaseModel):
    status: SessionStatus
