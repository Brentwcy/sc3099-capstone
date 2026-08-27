from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.device import DevicePlatform, DeviceTrustScore


class DeviceRegister(BaseModel):
    device_fingerprint: str = Field(min_length=8, max_length=64)
    device_name: str | None = Field(default=None, max_length=255)
    platform: DevicePlatform | None = None
    public_key: str = Field(min_length=32, max_length=16_384)

    @field_validator("device_fingerprint")
    @classmethod
    def normalize_fingerprint(cls, value: str) -> str:
        value = value.strip()
        if any(character.isspace() for character in value):
            raise ValueError("Device fingerprint cannot contain whitespace")
        return value


class DeviceUpdate(BaseModel):
    device_name: str | None = Field(default=None, max_length=255)
    is_trusted: bool | None = None
    is_active: bool | None = None


class DeviceResponse(BaseModel):
    id: str
    device_fingerprint: str
    device_name: str | None
    platform: DevicePlatform | None
    browser: str | None
    os_version: str | None
    app_version: str | None
    is_trusted: bool
    trust_score: DeviceTrustScore
    is_emulator: bool
    is_rooted_jailbroken: bool
    is_active: bool
    first_seen_at: datetime
    last_seen_at: datetime
    total_checkins: int

    model_config = ConfigDict(from_attributes=True)
