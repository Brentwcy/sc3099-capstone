from typing import Any

from pydantic import BaseModel, Field


class FaceEnrollRequest(BaseModel):
    user_id: str
    image: str
    camera_consent: bool


class FaceEnrollResult(BaseModel):
    enrollment_successful: bool
    face_template_hash: str | None = None
    quality_score: float = Field(ge=0, le=1)
    details: dict[str, Any] = Field(default_factory=dict)


class FaceVerifyRequest(BaseModel):
    image: str
    reference_template_hash: str


class FaceVerifyResult(BaseModel):
    match_passed: bool
    match_score: float = Field(ge=0, le=1)
    match_threshold: float = Field(default=0.7, ge=0, le=1)
    face_detected: bool
    current_template_hash: str | None = None


class LivenessRequest(BaseModel):
    challenge_response: str
    challenge_type: str = "passive"


class LivenessResult(BaseModel):
    liveness_passed: bool | None
    liveness_score: float = Field(ge=0, le=1)
    liveness_threshold: float = Field(default=0.6, ge=0, le=1)
    challenge_type: str = "passive"
    face_embedding_hash: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
