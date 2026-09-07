import hashlib
from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.schemas.face import (
    BiometricRiskResult,
    FaceEnrollResult,
    FaceVerifyResult,
    LivenessResult,
)
from app.services.face_client import FaceService, HttpFaceService


class ContractCompatibleFaceServiceMock:
    """Deterministic Week 4 stand-in; it never persists or logs image data."""

    async def enroll_face(
        self, *, user_id: str, image: str, camera_consent: bool
    ) -> FaceEnrollResult:
        return FaceEnrollResult(
            enrollment_successful=camera_consent,
            face_template_hash=(
                hashlib.sha256(f"mock-face:{user_id}".encode()).hexdigest()
                if camera_consent
                else None
            ),
            quality_score=0.92,
            details={"provider": "module3-contract-mock"},
        )

    async def verify_face(
        self, *, image: str, reference_template_hash: str
    ) -> FaceVerifyResult:
        return FaceVerifyResult(
            match_passed=True,
            match_score=0.92,
            match_threshold=0.7,
            face_detected=True,
            face_count=1,
        )

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

    async def assess_biometric_risk(
        self, *, liveness_score: float, face_match_score: float
    ) -> BiometricRiskResult:
        risk_score = round(
            0.5 * (1.0 - liveness_score) + 0.5 * (1.0 - face_match_score),
            4,
        )
        if risk_score < 0.3:
            risk_level = "LOW"
        elif risk_score < 0.5:
            risk_level = "MEDIUM"
        elif risk_score < 0.7:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"
        return BiometricRiskResult(
            risk_score=risk_score,
            risk_level=risk_level,
            pass_threshold=risk_score < 0.5,
            risk_threshold=0.5,
            signal_breakdown={
                "liveness": round(0.5 * (1.0 - liveness_score), 4),
                "face_match": round(0.5 * (1.0 - face_match_score), 4),
            },
            recommendations=[],
        )


@lru_cache
def get_mock_face_service() -> ContractCompatibleFaceServiceMock:
    return ContractCompatibleFaceServiceMock()


_http_face_service: HttpFaceService | None = None


def get_face_service(
    settings: Settings = Depends(get_settings),
) -> FaceService:
    global _http_face_service
    if settings.face_service_mode == "mock":
        return get_mock_face_service()
    if _http_face_service is None:
        _http_face_service = HttpFaceService(
            base_url=settings.face_service_url,
            connect_timeout_seconds=settings.face_connect_timeout_seconds,
            read_timeout_seconds=settings.face_read_timeout_seconds,
        )
    return _http_face_service


async def close_face_service() -> None:
    global _http_face_service
    if _http_face_service is not None:
        await _http_face_service.aclose()
        _http_face_service = None
