"""Tests for authoritative ``/users/me`` session validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from tests.fakes import APP_DIR, fake_streamlit, set_authenticated

from api_client import (
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
)
from components.auth import validate_authenticated_session


if "main" not in sys.modules:
    fake_pages = ModuleType("pages")
    fake_pages.render_page = lambda page, user: None
    sys.modules["pages"] = fake_pages

import main  # noqa: E402  (a fake page boundary is installed first when needed)


class ProfileClient:
    """Return or raise a configured current-user response."""

    def __init__(self, profile: object) -> None:
        self.profile = profile
        self.me_tokens: list[str] = []

    def get_current_user(self, access_token: str) -> object:
        self.me_tokens.append(access_token)
        if isinstance(self.profile, Exception):
            raise self.profile
        return self.profile


class RefreshThenProfileClient:
    """Return an initial 401, refresh once, then return a configured result."""

    def __init__(self, retry_result: object) -> None:
        self.retry_result = retry_result
        self.me_tokens: list[str] = []
        self.refresh_tokens: list[str] = []

    def get_current_user(self, access_token: str) -> object:
        self.me_tokens.append(access_token)
        if access_token == "access-old":
            raise APIResponseError(status_code=401, detail="expired")
        if isinstance(self.retry_result, Exception):
            raise self.retry_result
        return self.retry_result

    def refresh(self, refresh_token: str) -> dict[str, str]:
        self.refresh_tokens.append(refresh_token)
        return {
            "access_token": "access-new",
            "refresh_token": "refresh-new",
            "token_type": "bearer",
        }


class FailedRefreshClient:
    """Fail authentication and then fail the refresh exchange."""

    def __init__(self) -> None:
        self.refresh_calls = 0

    def get_current_user(self, access_token: str) -> object:
        raise APIResponseError(status_code=401, detail="expired")

    def refresh(self, refresh_token: str) -> dict[str, str]:
        self.refresh_calls += 1
        raise APIResponseError(status_code=401, detail="invalid refresh")


class SessionValidationTests(unittest.TestCase):
    """Verify server-authoritative profile state and safe failure routing."""

    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated()

    def test_success_updates_current_user_and_role_for_all_four_roles(self) -> None:
        for role in ("student", "ta", "instructor", "admin"):
            with self.subTest(role=role):
                fake_streamlit.reset()
                set_authenticated("instructor")
                profile = {
                    "id": role,
                    "email": f"{role}@example.com",
                    "full_name": role.title(),
                    "role": role,
                }

                self.assertIsNone(validate_authenticated_session(ProfileClient(profile)))

                self.assertEqual(fake_streamlit.session_state.current_user, profile)
                self.assertEqual(fake_streamlit.session_state.role, role)
                self.assertTrue(fake_streamlit.session_state.authenticated)

    def test_malformed_profile_clears_authentication(self) -> None:
        for profile in ([], {}, {"id": "missing-role"}):
            with self.subTest(profile=profile):
                fake_streamlit.reset()
                set_authenticated()

                message = validate_authenticated_session(ProfileClient(profile))

                self.assertIn("invalid profile", message)
                self.assertFalse(fake_streamlit.session_state.authenticated)
                self.assertIsNone(fake_streamlit.session_state.current_user)
                self.assertIsNone(fake_streamlit.session_state.role)

    def test_invalid_role_clears_authentication(self) -> None:
        message = validate_authenticated_session(
            ProfileClient({"id": "1", "role": "owner"})
        )

        self.assertIn("invalid profile", message)
        self.assertFalse(fake_streamlit.session_state.authenticated)

    def test_expired_access_uses_existing_refresh_retry_and_replacement_pair(self) -> None:
        client = RefreshThenProfileClient({"id": "student", "role": "student"})

        self.assertIsNone(validate_authenticated_session(client))

        self.assertEqual(client.me_tokens, ["access-old", "access-new"])
        self.assertEqual(client.refresh_tokens, ["refresh-old"])
        self.assertEqual(fake_streamlit.session_state.access_token, "access-new")
        self.assertEqual(fake_streamlit.session_state.refresh_token, "refresh-new")
        self.assertEqual(fake_streamlit.session_state.role, "student")

    def test_second_users_me_401_clears_auth_and_does_not_loop(self) -> None:
        client = RefreshThenProfileClient(
            APIResponseError(status_code=401, detail="still unauthorized")
        )

        message = validate_authenticated_session(client)

        self.assertIn("sign in again", message)
        self.assertEqual(client.me_tokens, ["access-old", "access-new"])
        self.assertEqual(client.refresh_tokens, ["refresh-old"])
        self.assertFalse(fake_streamlit.session_state.authenticated)

    def test_failed_refresh_routes_main_back_to_login(self) -> None:
        client = FailedRefreshClient()

        with (
            patch.object(main, "APIClient", return_value=client),
            patch.object(main, "render_login") as login_view,
            patch.object(main, "render_sidebar") as protected_navigation,
            patch.object(main, "render_page") as protected_page,
        ):
            main.main()

        self.assertEqual(client.refresh_calls, 1)
        self.assertFalse(fake_streamlit.session_state.authenticated)
        login_view.assert_called_once_with(client)
        protected_navigation.assert_not_called()
        protected_page.assert_not_called()

    def test_disabled_account_clears_authentication_safely(self) -> None:
        message = validate_authenticated_session(
            ProfileClient(APIResponseError(status_code=403, detail="Account disabled"))
        )

        self.assertIn("disabled or unavailable", message)
        self.assertFalse(fake_streamlit.session_state.authenticated)
        self.assertIsNone(fake_streamlit.session_state.access_token)
        self.assertIsNone(fake_streamlit.session_state.refresh_token)

    def test_transient_failures_do_not_expose_protected_content(self) -> None:
        cases = (
            (
                APIResponseError(
                    status_code=429,
                    detail="Rate limit exceeded",
                    retry_after="11",
                ),
                "rate limited",
            ),
            (APIResponseError(status_code=503, detail="unavailable"), "unavailable"),
            (APITimeoutError("timeout"), "timed out"),
            (APIConnectionError("offline"), "unreachable"),
        )
        for error, expected_message in cases:
            with self.subTest(error=type(error).__name__):
                fake_streamlit.reset()
                set_authenticated()
                client = ProfileClient(error)

                with (
                    patch.object(main, "APIClient", return_value=client),
                    patch.object(main, "render_sidebar") as protected_navigation,
                    patch.object(main, "render_page") as protected_page,
                ):
                    main.main()

                self.assertTrue(fake_streamlit.session_state.authenticated)
                self.assertTrue(
                    any(expected_message in message for message in fake_streamlit.errors)
                )
                protected_navigation.assert_not_called()
                protected_page.assert_not_called()

    def test_successful_validation_is_cached_until_access_token_changes(self) -> None:
        client = ProfileClient({"id": "1", "role": "instructor"})

        self.assertIsNone(validate_authenticated_session(client))
        self.assertIsNone(validate_authenticated_session(client))
        self.assertEqual(client.me_tokens, ["access-old"])

        fake_streamlit.session_state.access_token = "externally-replaced-access"
        self.assertIsNone(validate_authenticated_session(client))
        self.assertEqual(
            client.me_tokens,
            ["access-old", "externally-replaced-access"],
        )

    def test_application_does_not_decode_jwt_or_load_signing_secret(self) -> None:
        forbidden_fragments = (
            "jwt.decode",
            "decode_token",
            "from jose",
            "import jwt",
            "secret_key",
        )
        source = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in Path(APP_DIR).rglob("*.py")
        )

        for fragment in forbidden_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, source)


if __name__ == "__main__":
    unittest.main()
