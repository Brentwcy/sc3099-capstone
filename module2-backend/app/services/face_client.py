from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.schemas.face import (
    FaceEnrollRequest,
    FaceEnrollResult,
    FaceVerifyRequest,
    FaceVerifyResult,
    LivenessRequest,
    LivenessResult,
)


class FaceServiceError(Exception):
    """Base exception whose message is always safe to return to an API caller."""


class FaceServiceRejected(FaceServiceError):
    pass


class FaceServiceUnavailable(FaceServiceError):
    pass


class FaceServiceContractError(FaceServiceError):
    pass


class FaceService(Protocol):
    async def enroll_face(
        self, *, user_id: str, image: str, camera_consent: bool
    ) -> FaceEnrollResult: ...

    async def verify_face(
        self, *, image: str, reference_template_hash: str
    ) -> FaceVerifyResult: ...

    async def check_liveness(
        self,
        *,
        challenge_response: str,
        challenge_type: str = "passive",
    ) -> LivenessResult: ...


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class HttpFaceService:
    """Reusable Module 3 client; image strings are sent in memory and never logged."""

    def __init__(
        self,
        *,
        base_url: str,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(
                connect=connect_timeout_seconds,
                read=read_timeout_seconds,
                write=read_timeout_seconds,
                pool=connect_timeout_seconds,
            ),
        )

    async def _post(
        self,
        path: str,
        payload: BaseModel,
        response_model: type[ResponseModel],
        *,
        success_statuses: set[int] = {200},
    ) -> ResponseModel:
        try:
            response = await self._client.post(path, json=payload.model_dump())
        except httpx.TimeoutException as exc:
            raise FaceServiceUnavailable("Face service timed out") from exc
        except httpx.RequestError as exc:
            raise FaceServiceUnavailable("Face service is unavailable") from exc

        if response.status_code == 400:
            raise FaceServiceRejected("Face service rejected the submitted image")
        if response.status_code >= 500:
            raise FaceServiceUnavailable("Face service is unavailable")
        if response.status_code not in success_statuses:
            raise FaceServiceContractError("Face service returned an unexpected status")
        try:
            return response_model.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise FaceServiceContractError(
                "Face service returned an invalid response"
            ) from exc

    async def enroll_face(
        self, *, user_id: str, image: str, camera_consent: bool
    ) -> FaceEnrollResult:
        return await self._post(
            "/face/enroll",
            FaceEnrollRequest(
                user_id=user_id,
                image=image,
                camera_consent=camera_consent,
            ),
            FaceEnrollResult,
            success_statuses={200, 201},
        )

    async def verify_face(
        self, *, image: str, reference_template_hash: str
    ) -> FaceVerifyResult:
        return await self._post(
            "/face/verify",
            FaceVerifyRequest(
                image=image,
                reference_template_hash=reference_template_hash,
            ),
            FaceVerifyResult,
        )

    async def check_liveness(
        self,
        *,
        challenge_response: str,
        challenge_type: str = "passive",
    ) -> LivenessResult:
        return await self._post(
            "/liveness/check",
            LivenessRequest(
                challenge_response=challenge_response,
                challenge_type=challenge_type,
            ),
            LivenessResult,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
