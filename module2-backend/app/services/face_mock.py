from functools import lru_cache
from typing import Protocol

from pydantic import BaseModel, Field


class LivenessResult(BaseModel):
    """Subset of the documented Module 3 /liveness/check response."""

    liveness_passed: bool | None
    liveness_score: float = Field(ge=0, le=1)
    liveness_threshold: float = Field(default=0.6, ge=0, le=1)
    challenge_type: str = "passive"
    face_embedding_hash: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class FaceService(Protocol):
    async def check_liveness(
        self,
        *,
        challenge_response: str,
        challenge_type: str = "passive",
    ) -> LivenessResult: ...


class ContractCompatibleFaceServiceMock:
    """Deterministic Week 4 stand-in; it never persists or logs image data."""

    async def check_liveness(
        self,
        *,
        challenge_response: str,
        challenge_type: str = "passive",
    ) -> LivenessResult:
        return LivenessResult(
            liveness_passed=True,
            liveness_score=0.92,
            liveness_threshold=0.6,
            challenge_type=challenge_type,
            details={"provider": "module3-week4-mock"},
        )


@lru_cache
def get_face_service() -> ContractCompatibleFaceServiceMock:
    return ContractCompatibleFaceServiceMock()
