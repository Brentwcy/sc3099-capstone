from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.student

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be blank")
        return value


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    camera_consent: bool
    geolocation_consent: bool
    face_enrolled: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
    scheduled_deletion_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserSummary(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    face_enrolled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    camera_consent: bool | None = None
    geolocation_consent: bool | None = None

    @field_validator("full_name")
    @classmethod
    def sanitize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be blank")
        # Names are plain text. Reject markup rather than reflecting executable content.
        if "<" in value or ">" in value:
            raise ValueError("Full name cannot contain markup")
        return value


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class PaginatedUsers(BaseModel):
    items: list[UserSummary]
    total: int
    limit: int
    offset: int
