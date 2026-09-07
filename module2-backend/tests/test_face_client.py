import json

import httpx
import pytest

from app.services.face_client import (
    FaceServiceContractError,
    FaceServiceRejected,
    FaceServiceUnavailable,
    HttpFaceService,
)


def build_service(handler):
    client = httpx.AsyncClient(
        base_url="http://module3.test",
        transport=httpx.MockTransport(handler),
    )
    return (
        HttpFaceService(
            base_url="http://module3.test",
            connect_timeout_seconds=2,
            read_timeout_seconds=8,
            client=client,
        ),
        client,
    )


@pytest.mark.asyncio
async def test_http_face_client_reuses_client_and_validates_contract():
    seen_requests = []

    def handler(request):
        seen_requests.append(request)
        body = json.loads(request.content)
        assert body == {
            "challenge_response": "in-memory-image",
            "challenge_type": "passive",
        }
        return httpx.Response(
            200,
            json={
                "liveness_passed": True,
                "liveness_score": 0.91,
                "liveness_threshold": 0.6,
                "challenge_type": "passive",
                "details": {},
            },
        )

    service, client = build_service(handler)
    first = await service.check_liveness(challenge_response="in-memory-image")
    second = await service.check_liveness(challenge_response="in-memory-image")
    assert first.liveness_score == 0.91
    assert second.liveness_passed is True
    assert len(seen_requests) == 2
    assert all(request.url.path == "/liveness/check" for request in seen_requests)
    await client.aclose()


@pytest.mark.asyncio
async def test_http_face_client_requests_biometric_risk_from_module3():
    def handler(request):
        assert request.url.path == "/risk/assess"
        assert json.loads(request.content) == {
            "liveness_score": 0.8,
            "face_match_score": 0.6,
        }
        return httpx.Response(
            200,
            json={
                "risk_score": 0.3,
                "risk_level": "MEDIUM",
                "pass_threshold": True,
                "risk_threshold": 0.5,
                "signal_breakdown": {"liveness": 0.1, "face_match": 0.2},
                "recommendations": [],
            },
        )

    service, client = build_service(handler)
    result = await service.assess_biometric_risk(
        liveness_score=0.8,
        face_match_score=0.6,
    )
    assert result.risk_score == 0.3
    await client.aclose()


@pytest.mark.asyncio
async def test_http_face_client_preserves_multiple_face_verification_failure():
    def handler(request):
        assert request.url.path == "/face/verify"
        return httpx.Response(
            200,
            json={
                "match_passed": False,
                "match_score": 0.0,
                "match_threshold": 0.7,
                "face_detected": True,
                "face_count": 2,
                "failure_reason": "multiple_faces",
                "current_template_hash": "",
            },
        )

    service, client = build_service(handler)
    result = await service.verify_face(
        image="sensitive-image",
        reference_template_hash="a" * 64,
    )
    assert result.match_passed is False
    assert result.face_count == 2
    assert result.failure_reason == "multiple_faces"
    await client.aclose()


@pytest.mark.asyncio
async def test_http_face_client_rejects_inconsistent_face_count_contract():
    def handler(_request):
        return httpx.Response(
            200,
            json={
                "match_passed": True,
                "match_score": 0.9,
                "match_threshold": 0.7,
                "face_detected": True,
                "face_count": 2,
            },
        )

    service, client = build_service(handler)
    with pytest.raises(FaceServiceContractError, match="invalid response"):
        await service.verify_face(
            image="sensitive-image",
            reference_template_hash="a" * 64,
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_http_face_client_maps_timeout_without_exposing_image():
    image = "sensitive-image-content"

    def handler(request):
        raise httpx.ReadTimeout("read timed out", request=request)

    service, client = build_service(handler)
    with pytest.raises(FaceServiceUnavailable) as error:
        await service.check_liveness(challenge_response=image)
    assert str(error.value) == "Face service timed out"
    assert image not in str(error.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_http_face_client_maps_rejection_and_invalid_response():
    responses = iter(
        [
            httpx.Response(400, json={"detail": "raw provider detail"}),
            httpx.Response(200, json={"liveness_score": "invalid"}),
        ]
    )

    def handler(_request):
        return next(responses)

    service, client = build_service(handler)
    with pytest.raises(FaceServiceRejected, match="rejected the submitted image"):
        await service.check_liveness(challenge_response="image-one")
    with pytest.raises(FaceServiceContractError, match="invalid response"):
        await service.check_liveness(challenge_response="image-two")
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("face_template_hash", [None, "not-a-sha256-hash", "A" * 64])
async def test_http_face_client_rejects_successful_enrollment_without_valid_hash(
    face_template_hash,
):
    def handler(_request):
        return httpx.Response(
            201,
            json={
                "enrollment_successful": True,
                "face_template_hash": face_template_hash,
                "quality_score": 0.91,
                "details": {},
            },
        )

    service, client = build_service(handler)
    with pytest.raises(FaceServiceContractError, match="invalid response"):
        await service.enroll_face(
            user_id="student-id",
            image="sensitive-image",
            camera_consent=True,
        )
    await client.aclose()
