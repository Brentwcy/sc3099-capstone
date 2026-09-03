from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    app_name: str = "SAIV Backend API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    database_url: str = "sqlite:///./saiv.db"
    redis_url: str = "redis://localhost:6380/0"
    secret_key: str = "development-only-change-me-32-characters"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = Field(default=12, ge=10, le=16)
    cors_origins: str = "http://localhost:3000,http://localhost:8501"
    face_service_mode: str = "mock"
    face_service_url: str = "http://localhost:8001"
    face_connect_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    face_read_timeout_seconds: float = Field(default=8.0, gt=0, le=60)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        return value

    @field_validator("face_service_mode")
    @classmethod
    def validate_face_service_mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"mock", "http"}:
            raise ValueError("FACE_SERVICE_MODE must be 'mock' or 'http'")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
