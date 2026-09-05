from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CourseFields(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    semester: str = Field(min_length=1, max_length=20)
    venue_latitude: float | None = Field(default=None, ge=-90, le=90)
    venue_longitude: float | None = Field(default=None, ge=-180, le=180)
    venue_name: str | None = Field(default=None, max_length=255)
    geofence_radius_meters: float = Field(default=100.0, gt=0, le=10_000)
    require_face_recognition: bool = False
    require_device_binding: bool = True
    risk_threshold: float = Field(default=0.5, ge=0, le=1)

    @field_validator("name", "semester")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value or "<" in value or ">" in value:
            raise ValueError("Value must be non-blank plain text")
        return value

    @field_validator("description", "venue_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if "<" in value or ">" in value:
            raise ValueError("Value must be plain text")
        return value or None

    @model_validator(mode="after")
    def coordinates_are_paired(self):
        if (self.venue_latitude is None) != (self.venue_longitude is None):
            raise ValueError("Venue latitude and longitude must be provided together")
        return self


class CourseCreate(CourseFields):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CourseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    semester: str | None = Field(default=None, min_length=1, max_length=20)
    venue_latitude: float | None = Field(default=None, ge=-90, le=90)
    venue_longitude: float | None = Field(default=None, ge=-180, le=180)
    venue_name: str | None = Field(default=None, max_length=255)
    geofence_radius_meters: float | None = Field(default=None, gt=0, le=10_000)
    require_face_recognition: bool | None = None
    require_device_binding: bool | None = None
    risk_threshold: float | None = Field(default=None, ge=0, le=1)
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("name", "semester")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or "<" in value or ">" in value:
            raise ValueError("Value must be non-blank plain text")
        return value

    @field_validator("description", "venue_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if "<" in value or ">" in value:
            raise ValueError("Value must be plain text")
        return value or None


class CourseResponse(BaseModel):
    id: str
    code: str
    name: str
    description: str | None
    semester: str
    venue_latitude: float | None
    venue_longitude: float | None
    venue_name: str | None
    geofence_radius_meters: float
    require_face_recognition: bool
    require_device_binding: bool
    risk_threshold: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedCourses(BaseModel):
    items: list[CourseResponse]
    total: int
    limit: int
    offset: int
