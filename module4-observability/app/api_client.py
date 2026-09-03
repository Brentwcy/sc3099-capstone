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

    @staticmethod
    def _response_list(response: requests.Response) -> list[Any]:
        """Parse a successful backend response that must be a JSON list."""
        try:
            payload: Any = response.json()
        except requests.exceptions.JSONDecodeError:
            raise APIClientError("Backend returned an invalid JSON response") from None
        if not isinstance(payload, list):
            raise APIClientError("Backend returned an invalid response")
        return payload

    @staticmethod
    def _defined_params(**params: Any) -> dict[str, Any]:
        """Return query parameters whose values are explicitly defined."""
        return {key: value for key, value in params.items() if value is not None}

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

    def get_courses(
        self,
        access_token: str,
        *,
        is_active: bool | None = True,
        semester: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return the authenticated course listing."""
        response = self.get(
            "/api/v1/courses/",
            params=self._defined_params(
                is_active=is_active,
                semester=semester,
                limit=limit,
                offset=offset,
            ),
            access_token=access_token,
        )
        return self._response_object(response)

    def get_course(self, access_token: str, course_id: str) -> dict[str, Any]:
        """Return one course by ID."""
        response = self.get(
            f"/api/v1/courses/{course_id}",
            access_token=access_token,
        )
        return self._response_object(response)

    def get_sessions(
        self,
        access_token: str,
        *,
        status: str | None = None,
        course_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return the authenticated session listing."""
        response = self.get(
            "/api/v1/sessions/",
            params=self._defined_params(
                status=status,
                course_id=course_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
            ),
            access_token=access_token,
        )
        return self._response_object(response)

    def get_my_sessions(
        self,
        access_token: str,
        *,
        status: str | None = None,
        upcoming: bool = False,
        limit: int = 50,
    ) -> list[Any]:
        """Return sessions relevant to the authenticated user."""
        response = self.get(
            "/api/v1/sessions/my-sessions",
            params=self._defined_params(
                status=status,
                upcoming=upcoming,
                limit=limit,
            ),
            access_token=access_token,
        )
        return self._response_list(response)

    def get_session(self, access_token: str, session_id: str) -> dict[str, Any]:
        """Return one session by ID."""
        response = self.get(
            f"/api/v1/sessions/{session_id}",
            access_token=access_token,
        )
        return self._response_object(response)

    def get_my_checkins(
        self,
        access_token: str,
        *,
        course_id: str | None = None,
        limit: int = 50,
    ) -> list[Any]:
        """Return the authenticated student's check-in history."""
        response = self.get(
            "/api/v1/checkins/my-checkins",
            params=self._defined_params(course_id=course_id, limit=limit),
            access_token=access_token,
        )
        return self._response_list(response)

    def get_checkins(
        self,
        access_token: str,
        *,
        session_id: str | None = None,
        course_id: str | None = None,
        student_id: str | None = None,
        status: str | None = None,
        min_risk_score: float | None = None,
        max_risk_score: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return the authenticated check-in listing."""
        response = self.get(
            "/api/v1/checkins/",
            params=self._defined_params(
                session_id=session_id,
                course_id=course_id,
                student_id=student_id,
                status=status,
                min_risk_score=min_risk_score,
                max_risk_score=max_risk_score,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
            ),
            access_token=access_token,
        )
        return self._response_object(response)

    def get_checkin(self, access_token: str, checkin_id: str) -> dict[str, Any]:
        """Return one check-in by ID."""
        response = self.get(
            f"/api/v1/checkins/{checkin_id}",
            access_token=access_token,
        )
        return self._response_object(response)

    def get_session_checkins(
        self,
        access_token: str,
        session_id: str,
    ) -> list[Any]:
        """Return check-ins for one session."""
        response = self.get(
            f"/api/v1/checkins/session/{session_id}",
            access_token=access_token,
        )
        return self._response_list(response)

    def get_my_enrollments(self, access_token: str) -> list[Any]:
        """Return the authenticated student's enrollments."""
        response = self.get(
            "/api/v1/enrollments/my-enrollments",
            access_token=access_token,
        )
        return self._response_list(response)

    def get_course_enrollments(
        self,
        access_token: str,
        course_id: str,
        *,
        is_active: bool | None = True,
        search: str | None = None,
    ) -> dict[str, Any]:
        """Return the enrollment roster for one course."""
        response = self.get(
            f"/api/v1/enrollments/course/{course_id}",
            params=self._defined_params(is_active=is_active, search=search),
            access_token=access_token,
        )
        return self._response_object(response)

    def get_audit_logs(
        self,
        access_token: str,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        success: bool | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return the filtered audit-log listing."""
        response = self.get(
            "/api/v1/audit/",
            params=self._defined_params(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                success=success,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
            ),
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
