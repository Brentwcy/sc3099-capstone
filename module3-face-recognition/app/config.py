"""
Configuration management for SAIV Face Recognition & Risk Service.
Uses pydantic-settings for robust environment variable management.
"""
from typing import Optional
import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings
    SettingsConfigDict = None


class Settings(BaseSettings):
    """Application settings and environment configurations."""
    
    # Service Info
    SERVICE_NAME: str = "SAIV Face Recognition Service"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # External Services
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", "redis://redis:6379")
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    
    # Biometric Thresholds
    FACE_MATCH_THRESHOLD: float = 0.70
    LIVENESS_THRESHOLD: float = 0.60
    RISK_THRESHOLD: float = 0.50
    MIN_DETECTION_CONFIDENCE: float = 0.50
    
    # Logging
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    if SettingsConfigDict:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )


settings = Settings()
