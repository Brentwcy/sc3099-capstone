"""Focused tests for the reusable Module 4 backend client."""

from __future__ import annotations

import unittest

from tests.fakes import (
    FakeConnectionError,
    FakeResponse,
    FakeTimeout,
    fake_requests,
)

from api_client import (
    APIClient,
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
)
from config import BACKEND_URL


class APIClientRequestTests(unittest.TestCase):
    """Verify construction and safe error translation at the HTTP boundary."""

    def setUp(self) -> None:
        fake_requests.reset()

    def test_get_uses_configured_base_url_params_headers_timeout_and_bearer(self) -> None:
        fake_requests.queue(FakeResponse(payload={"ok": True}))
        client = APIClient(timeout=7.5)

        client.get(
            "/items",
            params={"page": 2},
            headers={"X-Trace": "trace-id"},
            access_token="access-token",
        )

        self.assertEqual(client.base_url, BACKEND_URL)
        self.assertEqual(
            fake_requests.calls,
            [
                {
                    "method": "GET",
                    "url": f"{BACKEND_URL}/items",
                    "json": None,
                    "params": {"page": 2},
                    "timeout": 7.5,
                    "headers": {
                        "X-Trace": "trace-id",
                        "Authorization": "Bearer access-token",
                    },
                }
            ],
        )

    def test_post_constructs_json_params_custom_headers_and_override_timeout(self) -> None:
        fake_requests.queue(FakeResponse())
        client = APIClient(base_url="http://backend.example/", timeout=3.0)

        client.post(
            "records",
            json={"value": 42},
            params={"dry_run": True},
            headers={"X-Request-ID": "request-id"},
            timeout=(1.0, 4.0),
        )

        self.assertEqual(
            fake_requests.calls[0],
            {
                "method": "POST",
                "url": "http://backend.example/records",
                "json": {"value": 42},
                "params": {"dry_run": True},
                "timeout": (1.0, 4.0),
                "headers": {"X-Request-ID": "request-id"},
            },
        )

    def test_patch_constructs_json_body(self) -> None:
        fake_requests.queue(FakeResponse())
        client = APIClient(base_url="http://backend.example")

        client.patch("/records/1", json={"flagged": True})

        self.assertEqual(fake_requests.calls[0]["method"], "PATCH")
        self.assertEqual(fake_requests.calls[0]["url"], "http://backend.example/records/1")
        self.assertEqual(fake_requests.calls[0]["json"], {"flagged": True})

    def test_http_error_preserves_status_and_detail(self) -> None:
        fake_requests.queue(FakeResponse(403, {"detail": "Account disabled"}))

        with self.assertRaises(APIResponseError) as raised:
            APIClient().get("/protected")

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "Account disabled")

    def test_rate_limit_error_preserves_retry_after(self) -> None:
        fake_requests.queue(
            FakeResponse(
                429,
                {"detail": "Rate limit exceeded"},
                headers={"Retry-After": "30"},
            )
        )

        with self.assertRaises(APIResponseError) as raised:
            APIClient().get("/protected")

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.detail, "Rate limit exceeded")
        self.assertEqual(raised.exception.retry_after, "30")

    def test_timeout_is_translated(self) -> None:
        fake_requests.queue(FakeTimeout("slow backend"))

        with self.assertRaises(APITimeoutError):
            APIClient().get("/health")

    def test_connection_failure_is_translated(self) -> None:
        fake_requests.queue(FakeConnectionError("offline"))

        with self.assertRaises(APIConnectionError):
            APIClient().get("/health")


class Week3ReadAPIContractTests(unittest.TestCase):
    """Pin the stable Week 3 read endpoints and query parameters."""

    def setUp(self) -> None:
        fake_requests.reset()
        self.client = APIClient(base_url="http://backend.example")

    def assert_get_call(
        self,
        index: int,
        path: str,
        params: dict[str, object] | None,
    ) -> None:
        call = fake_requests.calls[index]
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["url"], f"http://backend.example{path}")
        self.assertEqual(call["params"], params)
        self.assertEqual(call["headers"], {"Authorization": "Bearer access-token"})

    def test_course_interfaces_use_exact_routes_and_omit_none_params(self) -> None:
        courses = {"items": [], "total": 0, "limit": 25, "offset": 5}
        course = {"id": "course-1"}
        fake_requests.queue(
            FakeResponse(payload=courses),
            FakeResponse(payload=course),
        )

        self.assertEqual(
            self.client.get_courses(
                "access-token",
                is_active=False,
                semester=None,
                limit=25,
                offset=5,
            ),
            courses,
        )
        self.assertEqual(self.client.get_course("access-token", "course-1"), course)

        self.assert_get_call(
            0,
            "/api/v1/courses/",
            {"is_active": False, "limit": 25, "offset": 5},
        )
        self.assert_get_call(1, "/api/v1/courses/course-1", None)

    def test_session_interfaces_preserve_false_and_use_exact_routes(self) -> None:
        sessions = {"items": [], "total": 0, "limit": 10, "offset": 2}
        my_sessions: list[object] = []
        session = {"id": "session-1"}
        fake_requests.queue(
            FakeResponse(payload=sessions),
            FakeResponse(payload=my_sessions),
            FakeResponse(payload=session),
        )

        self.client.get_sessions(
            "access-token",
            status="active",
            course_id=None,
            start_date="2026-09-01T00:00:00Z",
            end_date=None,
            limit=10,
            offset=2,
        )
        self.client.get_my_sessions("access-token", status=None, upcoming=False, limit=20)
        self.client.get_session("access-token", "session-1")

        self.assert_get_call(
            0,
            "/api/v1/sessions/",
            {
                "status": "active",
                "start_date": "2026-09-01T00:00:00Z",
                "limit": 10,
                "offset": 2,
            },
        )
        self.assert_get_call(
            1,
            "/api/v1/sessions/my-sessions",
            {"upcoming": False, "limit": 20},
        )
        self.assert_get_call(2, "/api/v1/sessions/session-1", None)

    def test_checkin_interfaces_use_exact_routes_and_clean_params(self) -> None:
        fake_requests.queue(
            FakeResponse(payload=[]),
            FakeResponse(payload={"items": [], "total": 0, "limit": 50, "offset": 0}),
            FakeResponse(payload={"id": "checkin-1"}),
            FakeResponse(payload=[]),
        )

        self.client.get_my_checkins("access-token", course_id=None, limit=25)
        self.client.get_checkins(
            "access-token",
            session_id="session-1",
            course_id=None,
            student_id=None,
            status="flagged",
            min_risk_score=0.0,
            max_risk_score=None,
            start_date=None,
            end_date=None,
        )
        self.client.get_checkin("access-token", "checkin-1")
        self.client.get_session_checkins("access-token", "session-1")

        self.assert_get_call(
            0,
            "/api/v1/checkins/my-checkins",
            {"limit": 25},
        )
        self.assert_get_call(
            1,
            "/api/v1/checkins/",
            {
                "session_id": "session-1",
                "status": "flagged",
                "min_risk_score": 0.0,
                "limit": 50,
                "offset": 0,
            },
        )
        self.assert_get_call(2, "/api/v1/checkins/checkin-1", None)
        self.assert_get_call(3, "/api/v1/checkins/session/session-1", None)

    def test_enrollment_interfaces_preserve_false_and_omit_none(self) -> None:
        fake_requests.queue(
            FakeResponse(payload=[]),
            FakeResponse(payload={"course_id": "course-1", "students": []}),
        )

        self.client.get_my_enrollments("access-token")
        self.client.get_course_enrollments(
            "access-token",
            "course-1",
            is_active=False,
            search=None,
        )

        self.assert_get_call(0, "/api/v1/enrollments/my-enrollments", None)
        self.assert_get_call(
            1,
            "/api/v1/enrollments/course/course-1",
            {"is_active": False},
        )

    def test_audit_interface_preserves_false_and_omits_none_params(self) -> None:
        logs = {"items": [], "total": 0, "limit": 10, "offset": 3}
        fake_requests.queue(FakeResponse(payload=logs))

        self.assertEqual(
            self.client.get_audit_logs(
                "access-token",
                user_id=None,
                action="login_failed",
                resource_type=None,
                resource_id=None,
                success=False,
                start_date=None,
                end_date=None,
                limit=10,
                offset=3,
            ),
            logs,
        )

        self.assert_get_call(
            0,
            "/api/v1/audit/",
            {"action": "login_failed", "success": False, "limit": 10, "offset": 3},
        )


class AuthAPIContractTests(unittest.TestCase):
    """Pin the confirmed Module 2 authentication request contracts."""

    def setUp(self) -> None:
        fake_requests.reset()
        self.client = APIClient(base_url="http://backend.example")

    def test_login_posts_exact_endpoint_and_json(self) -> None:
        payload = {
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "bearer",
            "user": {"role": "student"},
        }
        fake_requests.queue(FakeResponse(payload=payload))

        result = self.client.login("user@example.com", "password")

        self.assertEqual(result, payload)
        call = fake_requests.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "http://backend.example/api/v1/auth/login")
        self.assertEqual(
            call["json"],
            {"email": "user@example.com", "password": "password"},
        )

    def test_refresh_posts_json_without_bearer_header(self) -> None:
        payload = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "token_type": "bearer",
        }
        fake_requests.queue(FakeResponse(payload=payload))

        result = self.client.refresh("stored-refresh")

        self.assertEqual(result, payload)
        call = fake_requests.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "http://backend.example/api/v1/auth/refresh")
        self.assertEqual(call["json"], {"refresh_token": "stored-refresh"})
        self.assertNotIn("Authorization", call["headers"])

    def test_current_user_gets_exact_endpoint_with_access_bearer(self) -> None:
        user = {"id": "1", "role": "instructor"}
        fake_requests.queue(FakeResponse(payload=user))

        result = self.client.get_current_user("access-token")

        self.assertEqual(result, user)
        call = fake_requests.calls[0]
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["url"], "http://backend.example/api/v1/users/me")
        self.assertEqual(call["headers"], {"Authorization": "Bearer access-token"})

    def test_public_health_is_one_unauthenticated_request(self) -> None:
        fake_requests.queue(FakeResponse(payload={"status": "healthy"}))

        result = self.client.check_health()

        self.assertTrue(result["healthy"])
        self.assertEqual(len(fake_requests.calls), 1)
        call = fake_requests.calls[0]
        self.assertEqual(call["url"], "http://backend.example/health")
        self.assertNotIn("Authorization", call["headers"])


if __name__ == "__main__":
    unittest.main()
