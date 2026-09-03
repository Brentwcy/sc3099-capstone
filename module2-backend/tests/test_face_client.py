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
