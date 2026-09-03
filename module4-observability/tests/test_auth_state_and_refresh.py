"""Tests for Streamlit auth state and the one-refresh request wrapper."""

from __future__ import annotations

import unittest

from tests.fakes import fake_streamlit, login_payload, set_authenticated

from api_client import APIResponseError
from components.auth import (
    AuthStateError,
    VALID_ROLES,
    authenticated_request,
    clear_auth_state,
    initialize_auth_state,
    replace_tokens,
    store_login_response,
)


AUTH_DEFAULTS = {
    "access_token": None,
    "refresh_token": None,
    "current_user": None,
    "role": None,
    "authenticated": False,
}


class AuthStateTests(unittest.TestCase):
    """Verify atomic storage and clearing of per-session authentication."""

    def setUp(self) -> None:
        fake_streamlit.reset()

    def test_initialization_creates_all_logged_out_defaults(self) -> None:
        initialize_auth_state()

        self.assertEqual(fake_streamlit.session_state, AUTH_DEFAULTS)

    def test_initialization_does_not_overwrite_existing_session(self) -> None:
        existing = login_payload("ta")
        fake_streamlit.session_state.update(
            {
                "access_token": existing["access_token"],
                "refresh_token": existing["refresh_token"],
                "current_user": existing["user"],
                "role": "ta",
                "authenticated": True,
            }
        )

        initialize_auth_state()

        self.assertTrue(fake_streamlit.session_state.authenticated)
        self.assertEqual(fake_streamlit.session_state.role, "ta")
        self.assertEqual(fake_streamlit.session_state.access_token, "access-old")

    def test_successful_login_stores_all_five_fields(self) -> None:
        initialize_auth_state()
        payload = login_payload("instructor")

        store_login_response(payload)

        self.assertEqual(fake_streamlit.session_state.access_token, "access-old")
        self.assertEqual(fake_streamlit.session_state.refresh_token, "refresh-old")
        self.assertEqual(fake_streamlit.session_state.current_user, payload["user"])
        self.assertEqual(fake_streamlit.session_state.role, "instructor")
        self.assertTrue(fake_streamlit.session_state.authenticated)

    def test_valid_roles_are_exact_and_each_is_accepted(self) -> None:
        self.assertEqual(VALID_ROLES, {"student", "ta", "instructor", "admin"})

        for role in VALID_ROLES:
            with self.subTest(role=role):
                fake_streamlit.reset()
                initialize_auth_state()
                store_login_response(login_payload(role))
                self.assertEqual(fake_streamlit.session_state.role, role)
                self.assertTrue(fake_streamlit.session_state.authenticated)

    def test_malformed_login_or_invalid_role_leaves_no_partial_auth(self) -> None:
        malformed_payloads = (
            {},
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "token_type": "bearer",
            },
            login_payload("owner"),
        )
        for payload in malformed_payloads:
            with self.subTest(payload=payload):
                fake_streamlit.reset()
                set_authenticated()
                with self.assertRaises(AuthStateError):
                    store_login_response(payload)
                self.assertEqual(fake_streamlit.session_state, AUTH_DEFAULTS)

    def test_successful_refresh_replaces_both_tokens(self) -> None:
        set_authenticated()

        replace_tokens(
            {
                "access_token": "access-new",
                "refresh_token": "refresh-new",
                "token_type": "bearer",
            }
        )

        self.assertEqual(fake_streamlit.session_state.access_token, "access-new")
        self.assertEqual(fake_streamlit.session_state.refresh_token, "refresh-new")

    def test_clear_auth_state_clears_all_five_fields(self) -> None:
        set_authenticated("admin")

        clear_auth_state()

        self.assertEqual(fake_streamlit.session_state, AUTH_DEFAULTS)


class RefreshingClient:
    """Record refresh calls and return or raise the configured action."""

    def __init__(self, action: dict[str, str] | Exception | None = None) -> None:
        self.action = action or {
            "access_token": "access-new",
            "refresh_token": "refresh-new",
            "token_type": "bearer",
        }
        self.refresh_calls: list[str] = []

    def refresh(self, refresh_token: str) -> dict[str, str]:
        self.refresh_calls.append(refresh_token)
        if isinstance(self.action, Exception):
            raise self.action
        return self.action


class AuthenticatedRequestTests(unittest.TestCase):
    """Pin the single-refresh, single-retry behavior for protected requests."""

    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated()

    def test_valid_request_succeeds_without_refresh(self) -> None:
        client = RefreshingClient()
        operation_tokens: list[str] = []

        result = authenticated_request(
            client,
            lambda token: operation_tokens.append(token) or {"ok": True},
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(operation_tokens, ["access-old"])
        self.assertEqual(client.refresh_calls, [])

    def test_first_401_refreshes_once_stores_pair_and_retries_with_new_access(self) -> None:
        client = RefreshingClient()
        operation_tokens: list[str] = []

        def operation(token: str) -> str:
            operation_tokens.append(token)
            if token == "access-old":
                raise APIResponseError(status_code=401, detail="expired")
            return "success"

        result = authenticated_request(client, operation)

        self.assertEqual(result, "success")
        self.assertEqual(client.refresh_calls, ["refresh-old"])
        self.assertEqual(operation_tokens, ["access-old", "access-new"])
        self.assertEqual(fake_streamlit.session_state.access_token, "access-new")
        self.assertEqual(fake_streamlit.session_state.refresh_token, "refresh-new")

    def test_second_401_does_not_loop_and_clears_auth(self) -> None:
        client = RefreshingClient()
        operation_tokens: list[str] = []

        def always_unauthorized(token: str) -> None:
            operation_tokens.append(token)
            raise APIResponseError(status_code=401, detail="unauthorized")

        with self.assertRaises(APIResponseError):
            authenticated_request(client, always_unauthorized)

        self.assertEqual(client.refresh_calls, ["refresh-old"])
        self.assertEqual(operation_tokens, ["access-old", "access-new"])
        self.assertFalse(fake_streamlit.session_state.authenticated)

    def test_failed_refresh_clears_authentication(self) -> None:
        client = RefreshingClient(
            APIResponseError(status_code=503, detail="refresh unavailable")
        )

        def unauthorized(token: str) -> None:
            raise APIResponseError(status_code=401, detail="expired")

        with self.assertRaises(APIResponseError):
            authenticated_request(client, unauthorized)

        self.assertEqual(client.refresh_calls, ["refresh-old"])
        self.assertEqual(fake_streamlit.session_state, AUTH_DEFAULTS)

    def test_refresh_401_is_not_recursively_refreshed(self) -> None:
        client = RefreshingClient(
            APIResponseError(status_code=401, detail="invalid refresh token")
        )

        def unauthorized(token: str) -> None:
            raise APIResponseError(status_code=401, detail="expired")

        with self.assertRaises(APIResponseError):
            authenticated_request(client, unauthorized)

        self.assertEqual(client.refresh_calls, ["refresh-old"])
        self.assertFalse(fake_streamlit.session_state.authenticated)

    def test_non_401_errors_never_refresh(self) -> None:
        for status_code in (403, 422, 429, 503):
            with self.subTest(status_code=status_code):
                fake_streamlit.reset()
                set_authenticated()
                client = RefreshingClient()

                def operation(token: str) -> None:
                    raise APIResponseError(status_code=status_code, detail="error")

                with self.assertRaises(APIResponseError) as raised:
                    authenticated_request(client, operation)
                self.assertEqual(raised.exception.status_code, status_code)
                self.assertEqual(client.refresh_calls, [])


if __name__ == "__main__":
    unittest.main()
