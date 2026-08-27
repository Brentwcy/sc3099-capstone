"""Reusable HTTP client for the Module 2 backend."""

from collections.abc import Mapping
from typing import Any

import requests

from config import BACKEND_URL


RequestTimeout = float | tuple[float, float]


class APIClientError(Exception):
    """Base error for safe failures raised by the backend client."""


class APIResponseError(APIClientError):
    """An HTTP error response returned by the backend."""

    def __init__(
        self,
        *,
        status_code: int,
        detail: Any,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(f"Backend request failed with HTTP {status_code}")
        self.status_code = status_code
        self.detail = detail
        self.retry_after = retry_after


class APITimeoutError(APIClientError):
    """The backend did not respond within the configured timeout."""


class APIConnectionError(APIClientError):
    """The backend could not be reached."""


class APIClient:
    """Small client for public and bearer-authenticated backend requests."""

    def __init__(
        self,
        base_url: str = BACKEND_URL,
        timeout: RequestTimeout = 3.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _error_detail(response: requests.Response) -> Any:
        """Extract a useful, serializable detail from an error response."""
        try:
            payload: Any = response.json()
        except requests.exceptions.JSONDecodeError:
            return response.text or response.reason or "Backend request failed"

        if isinstance(payload, dict) and "detail" in payload:
            return payload["detail"]
        return payload

    @staticmethod
    def _response_object(response: requests.Response) -> dict[str, Any]:
        """Parse a successful backend response that must be a JSON object."""
        try:
            payload: Any = response.json()
        except requests.exceptions.JSONDecodeError:
            raise APIClientError("Backend returned an invalid JSON response") from None
        if not isinstance(payload, dict):
            raise APIClientError("Backend returned an invalid response")
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: RequestTimeout | None = None,
        headers: Mapping[str, str] | None = None,
        access_token: str | None = None,
        raise_for_status: bool = True,
    ) -> requests.Response:
        """Send one backend request and translate transport and HTTP errors."""
        request_headers = dict(headers or {})
        if access_token is not None:
            request_headers["Authorization"] = f"Bearer {access_token}"

        try:
            response = requests.request(
                method=method,
                url=f"{self.base_url}/{path.lstrip('/')}",
                json=json,
                params=params,
                timeout=self.timeout if timeout is None else timeout,
                headers=request_headers,
            )
        except requests.Timeout:
            raise APITimeoutError("Backend request timed out") from None
        except requests.ConnectionError:
            raise APIConnectionError("Backend is unavailable") from None
        except requests.RequestException:
            raise APIClientError("Backend request failed") from None

        if raise_for_status and response.status_code >= 400:
            raise APIResponseError(
                status_code=response.status_code,
                detail=self._error_detail(response),
                retry_after=response.headers.get("Retry-After"),
            )
        return response

    def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        timeout: RequestTimeout | None = None,
        headers: Mapping[str, str] | None = None,
        access_token: str | None = None,
        raise_for_status: bool = True,
    ) -> requests.Response:
        """Send a GET request to the backend."""
        return self._request(
            "GET",
            path,
            params=params,
            timeout=timeout,
            headers=headers,
            access_token=access_token,
            raise_for_status=raise_for_status,
        )

    def post(
        self,
        path: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: RequestTimeout | None = None,
        headers: Mapping[str, str] | None = None,
        access_token: str | None = None,
        raise_for_status: bool = True,
    ) -> requests.Response:
        """Send a POST request to the backend."""
        return self._request(
            "POST",
            path,
            json=json,
            params=params,
            timeout=timeout,
            headers=headers,
            access_token=access_token,
            raise_for_status=raise_for_status,
        )

    def patch(
        self,
        path: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: RequestTimeout | None = None,
        headers: Mapping[str, str] | None = None,
        access_token: str | None = None,
        raise_for_status: bool = True,
    ) -> requests.Response:
        """Send a PATCH request to the backend."""
        return self._request(
            "PATCH",
            path,
            json=json,
            params=params,
            timeout=timeout,
            headers=headers,
            access_token=access_token,
            raise_for_status=raise_for_status,
        )

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate with Module 2 and return its token-and-user response."""
        response = self.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        return self._response_object(response)

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        """Exchange a refresh token in the JSON body for a replacement pair."""
        response = self.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        return self._response_object(response)

    def get_current_user(self, access_token: str) -> dict[str, Any]:
        """Return the current user using the supplied access token."""
        response = self.get(
            "/api/v1/users/me",
            access_token=access_token,
        )
        return self._response_object(response)

    def check_health(self) -> dict[str, Any]:
        """Check the public Module 2 health endpoint without authentication."""
        try:
            response = self.get("/health", raise_for_status=False)
            try:
                payload: Any = response.json()
            except requests.exceptions.JSONDecodeError:
                payload = {"status": "invalid response"}

            return {
                "reachable": True,
                "healthy": response.ok,
                "status_code": response.status_code,
                "data": payload,
            }
        except APIClientError as exc:
            return {
                "reachable": False,
                "healthy": False,
                "status_code": None,
                "data": {},
                "error": str(exc),
            }
