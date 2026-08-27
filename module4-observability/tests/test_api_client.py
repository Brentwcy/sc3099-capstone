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
