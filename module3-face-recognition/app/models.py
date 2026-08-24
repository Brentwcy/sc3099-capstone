"""
Pydantic Request and Response Models for SAIV Face Recognition & Risk Service.
"""
from typing import Any
from pydantic import BaseModel, Field, model_validator


class FaceEnrollRequest(BaseModel):
    """Request model for face enrollment."""
    user_id: str = Field(..., description="UUID of the user being enrolled")
    image: str = Field(..., description="Base64 encoded face image")
    camera_consent: bool = Field(False, description="User consent for camera and biometric processing")


class FaceEnrollResponse(BaseModel):
    """Response model for face enrollment."""
    enrollment_successful: bool
    face_template_hash: str = Field("", description="64-char SHA-256 hex string")
    quality_score: float = Field(0.0, description="Quality score between 0.0 and 1.0")
    details: dict[str, Any] = Field(default_factory=dict)


class FaceVerifyRequest(BaseModel):
    """Request model for face verification."""
    image: str = Field(..., description="Base64 encoded image to verify")
    reference_template_hash: str | None = Field(None, description="64-char SHA-256 template hash from enrollment")
    reference_hash: str | None = Field(None, description="Legacy field name for reference_template_hash")

    @model_validator(mode="before")
    @classmethod
    def populate_reference_hash(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "reference_hash" in data and not data.get("reference_template_hash"):
                data["reference_template_hash"] = data["reference_hash"]
            elif "reference_template_hash" in data and not data.get("reference_hash"):
                data["reference_hash"] = data["reference_template_hash"]
        return data


class FaceVerifyResponse(BaseModel):
    """Response model for face verification."""
    match_passed: bool
    match_score: float = Field(..., description="Similarity score between 0.0 and 1.0")
    match_threshold: float = Field(0.70, description="Threshold required for match pass")
    face_detected: bool = True
    current_template_hash: str = Field("", description="SHA-256 hash of the verification image")
    face_embedding_hash: str | None = Field(None, description="Alias for current_template_hash")


class LivenessRequest(BaseModel):
    """Request model for liveness check."""
    challenge_response: str = Field(..., description="Base64 encoded face image")
    challenge_type: str = Field("passive", description="passive, blink, or head_turn")


class LivenessResponse(BaseModel):
    """Response model for liveness check."""
    liveness_passed: bool
    liveness_score: float = Field(..., description="Liveness score between 0.0 and 1.0")
    liveness_threshold: float = Field(0.60, description="Threshold required for liveness pass")
    challenge_type: str | None = "passive"
    face_embedding_hash: str = Field("", description="SHA-256 hash of the face template")
    details: dict[str, Any] = Field(default_factory=dict)


class GeolocationData(BaseModel):
    """Geolocation data for risk assessment."""
    latitude: float
    longitude: float
    accuracy: float = 10.0


class RiskAssessRequest(BaseModel):
    """Request model for multi-signal risk assessment."""
    liveness_score: Optional[float] = None
    face_match_score: Optional[float] = None
    device_signature: Optional[str] = None
    device_public_key: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    geolocation: "GeolocationData | None" = None


class RiskAssessResponse(BaseModel):
    """Response model for risk assessment."""
    risk_score: float = Field(..., description="Combined risk score between 0.0 and 1.0")
    risk_level: str = Field(..., description="LOW, MEDIUM, HIGH, or CRITICAL")
    pass_threshold: bool = Field(..., description="True if risk_score < risk_threshold")
    risk_threshold: float = Field(0.50, description="Risk threshold cutoff (default: 0.50)")
    signal_breakdown: dict[str, float] = Field(default_factory=dict)
    signals: dict[str, float] | None = None
    recommendations: list[str] = Field(default_factory=list)
