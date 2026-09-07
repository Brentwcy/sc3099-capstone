from typing import Any

from pydantic import BaseModel, Field, model_validator


SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"


class FaceEnrollRequest(BaseModel):
    user_id: str
    image: str
    camera_consent: bool


class FaceEnrollResult(BaseModel):
    enrollment_successful: bool
    face_template_hash: str | None = Field(default=None, pattern=SHA256_HEX_PATTERN)
    quality_score: float = Field(ge=0, le=1)
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def successful_enrollment_requires_hash(self) -> "FaceEnrollResult":
        if self.enrollment_successful and self.face_template_hash is None:
            raise ValueError("Successful face enrollment requires a template hash")
        return self


class UserFaceEnrollmentRequest(BaseModel):
    image: str = Field(min_length=1, max_length=15_000_000)


class FaceVerifyRequest(BaseModel):
    image: str
    reference_template_hash: str


class FaceVerifyResult(BaseModel):
    match_passed: bool
    match_score: float = Field(ge=0, le=1)
    match_threshold: float = Field(default=0.7, ge=0, le=1)
    face_detected: bool
    face_count: int = Field(default=1, ge=0)
    failure_reason: str | None = None
    current_template_hash: str | None = None

    @model_validator(mode="after")
    def validate_face_count_result(self) -> "FaceVerifyResult":
        if self.match_passed and (not self.face_detected or self.face_count != 1):
            raise ValueError("A successful match requires exactly one detected face")
        if self.failure_reason == "no_face" and (
            self.face_detected or self.face_count != 0
        ):
            raise ValueError("no_face requires face_detected=false and face_count=0")
        if self.failure_reason == "multiple_faces" and (
            not self.face_detected or self.face_count < 2
        ):
            raise ValueError(
                "multiple_faces requires face_detected=true and face_count>=2"
            )
        return self


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


class BiometricRiskRequest(BaseModel):
    liveness_score: float = Field(ge=0, le=1)
    face_match_score: float = Field(ge=0, le=1)


class BiometricRiskResult(BaseModel):
    risk_score: float = Field(ge=0, le=1)
    risk_level: str
    pass_threshold: bool
    risk_threshold: float = Field(default=0.5, ge=0, le=1)
    signal_breakdown: dict[str, float] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
