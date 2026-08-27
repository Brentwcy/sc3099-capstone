"""Tests for the login gate, role-aware navigation, and local logout."""

from __future__ import annotations

import sys
import unittest
from types import ModuleType
from unittest.mock import patch

from tests.fakes import fake_streamlit, login_payload, set_authenticated

from api_client import (
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
)
from components.auth import initialize_auth_state, render_login, store_login_response
from components.navigation import render_sidebar
from utils.permissions import ROLE_PAGE_PERMISSIONS, resolve_page


rendered_pages: list[tuple[str, dict[str, str]]] = []
fake_pages = ModuleType("pages")
fake_pages.render_page = lambda page, user: rendered_pages.append((page, dict(user)))
sys.modules["pages"] = fake_pages

import main  # noqa: E402  (the pages boundary must be replaced before import)


class LoginClient:
    """Configurable login client with refresh-call tracking."""

    def __init__(self, result: dict[str, object] | Exception) -> None:
        self.result = result
        self.login_calls: list[tuple[str, str]] = []
        self.refresh_calls: list[str] = []

    def login(self, email: str, password: str) -> dict[str, object]:
        self.login_calls.append((email, password))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def refresh(self, token: str) -> dict[str, str]:
        self.refresh_calls.append(token)
        raise AssertionError("login failures must not refresh")


class ProfileClient:
    """Return a fixed authoritative profile for main routing tests."""

    def __init__(self, role: str) -> None:
        self.user = {
            "id": "profile-id",
            "email": f"{role}@example.com",
            "role": role,
        }

    def get_current_user(self, access_token: str) -> dict[str, str]:
        return self.user


class LoginUITests(unittest.TestCase):
    """Verify the login form and unauthenticated dashboard gate."""

    def setUp(self) -> None:
        fake_streamlit.reset()
        initialize_auth_state()

    def submit_credentials(self, email: str, password: str) -> None:
        fake_streamlit.input_values.update({"Email": email, "Password": password})
        fake_streamlit.form_submitted = True

    def test_unauthenticated_main_shows_login_not_protected_content(self) -> None:
        client = LoginClient(login_payload())

        with (
            patch.object(main, "APIClient", return_value=client),
            patch.object(main, "render_login") as login_view,
            patch.object(main, "render_sidebar") as protected_navigation,
            patch.object(main, "render_page") as protected_page,
        ):
            main.main()

        login_view.assert_called_once_with(client)
        protected_navigation.assert_not_called()
        protected_page.assert_not_called()

    def test_empty_email_or_password_never_calls_backend(self) -> None:
        for email, password in (("", "password"), ("user@example.com", "")):
            with self.subTest(email=email, password=password):
                fake_streamlit.reset()
                initialize_auth_state()
                self.submit_credentials(email, password)
                client = LoginClient(login_payload())

                render_login(client)

                self.assertEqual(client.login_calls, [])
                self.assertFalse(fake_streamlit.session_state.authenticated)

    def test_password_field_is_masked(self) -> None:
        render_login(LoginClient(login_payload()))

        password_call = next(call for call in fake_streamlit.input_calls if call[0] == "Password")
        self.assertEqual(password_call[1].get("type"), "password")

    def test_login_http_errors_remain_logged_out_and_429_shows_retry_after(self) -> None:
        cases = {
            401: "Invalid email or password",
            403: "disabled or unavailable",
            422: "valid email address and password",
            429: "Retry after: 17",
        }
        for status_code, expected_message in cases.items():
            with self.subTest(status_code=status_code):
                fake_streamlit.reset()
                initialize_auth_state()
                self.submit_credentials("user@example.com", "password")
                client = LoginClient(
                    APIResponseError(
                        status_code=status_code,
                        detail="backend detail",
                        retry_after="17" if status_code == 429 else None,
                    )
                )

                render_login(client)

                self.assertFalse(fake_streamlit.session_state.authenticated)
                self.assertTrue(
                    any(expected_message in message for message in fake_streamlit.errors)
                )
                self.assertEqual(client.refresh_calls, [])

    def test_timeout_and_connection_failures_are_handled_without_authentication(self) -> None:
        cases = (
            (APITimeoutError("timeout"), "timed out"),
            (APIConnectionError("offline"), "unreachable"),
        )
        for error, expected_message in cases:
            with self.subTest(error=type(error).__name__):
                fake_streamlit.reset()
                initialize_auth_state()
                self.submit_credentials("user@example.com", "password")

                render_login(LoginClient(error))

                self.assertFalse(fake_streamlit.session_state.authenticated)
                self.assertTrue(
                    any(expected_message in message for message in fake_streamlit.errors)
                )

    def test_all_four_roles_authenticate_and_no_role_input_is_rendered(self) -> None:
        for role in ("student", "ta", "instructor", "admin"):
            with self.subTest(role=role):
                fake_streamlit.reset()
                initialize_auth_state()
                self.submit_credentials("user@example.com", "password")

                render_login(LoginClient(login_payload(role)))

                self.assertTrue(fake_streamlit.session_state.authenticated)
                self.assertEqual(fake_streamlit.session_state.role, role)
                self.assertEqual(
                    {label for label, _ in fake_streamlit.input_calls},
                    {"Email", "Password"},
                )


class RBACNavigationTests(unittest.TestCase):
    """Pin exact role page lists and stale-page protection."""

    def setUp(self) -> None:
        fake_streamlit.reset()
        rendered_pages.clear()

    def test_role_page_permissions_are_exact(self) -> None:
        self.assertEqual(
            ROLE_PAGE_PERMISSIONS,
            {
                "student": ("My Attendance", "Sessions"),
                "ta": ("Sessions", "Check-ins", "Flagged Review"),
                "instructor": (
                    "Overview",
                    "Sessions",
                    "Check-ins",
                    "Flagged Review",
                    "Analytics",
                    "Exports",
                ),
                "admin": ("Overview", "Audit Logs", "System Metrics"),
            },
        )

    def test_student_cannot_render_overview_analytics_or_exports(self) -> None:
        for forbidden_page in ("Overview", "Analytics", "Exports"):
            with self.subTest(page=forbidden_page):
                fake_streamlit.reset()
                rendered_pages.clear()
                set_authenticated("student")
                fake_streamlit.session_state.selected_page = forbidden_page

                with patch.object(main, "APIClient", return_value=ProfileClient("student")):
                    main.main()

                self.assertEqual(
                    fake_streamlit.sidebar.radio_options,
                    ("My Attendance", "Sessions"),
                )
                self.assertEqual(rendered_pages[0][0], "My Attendance")

    def test_ta_cannot_render_instructor_analytics_or_exports(self) -> None:
        for forbidden_page in ("Analytics", "Exports"):
            with self.subTest(page=forbidden_page):
                fake_streamlit.reset()
                rendered_pages.clear()
                set_authenticated("ta")
                fake_streamlit.session_state.selected_page = forbidden_page

                with patch.object(main, "APIClient", return_value=ProfileClient("ta")):
                    main.main()

                self.assertEqual(
                    fake_streamlit.sidebar.radio_options,
                    ("Sessions", "Check-ins", "Flagged Review"),
                )
                self.assertEqual(rendered_pages[0][0], "Sessions")

    def test_stale_instructor_page_is_rejected_after_server_role_change(self) -> None:
        set_authenticated("instructor")
        fake_streamlit.session_state.selected_page = "Analytics"

        with patch.object(main, "APIClient", return_value=ProfileClient("student")):
            main.main()

        self.assertEqual(fake_streamlit.session_state.role, "student")
        self.assertEqual(fake_streamlit.session_state.selected_page, "My Attendance")
        self.assertEqual(rendered_pages[0][0], "My Attendance")

    def test_navigation_has_no_role_selector_or_role_mutation(self) -> None:
        set_authenticated("admin")

        selected_page = render_sidebar()

        self.assertEqual(fake_streamlit.session_state.role, "admin")
        self.assertEqual(selected_page, "Overview")
        self.assertEqual(fake_streamlit.sidebar.radio_options, ROLE_PAGE_PERMISSIONS["admin"])
        self.assertIn(
            ("radio", ("Navigation", "selected_page")),
            fake_streamlit.sidebar.events,
        )

    def test_resolve_page_rejects_forbidden_requests(self) -> None:
        self.assertEqual(resolve_page("student", "Overview"), "My Attendance")
        self.assertEqual(resolve_page("student", "Analytics"), "My Attendance")
        self.assertEqual(resolve_page("student", "Exports"), "My Attendance")
        self.assertEqual(resolve_page("ta", "Analytics"), "Sessions")
        self.assertEqual(resolve_page("ta", "Exports"), "Sessions")


class LogoutTests(unittest.TestCase):
    """Verify complete local logout and navigation-state isolation."""

    def setUp(self) -> None:
        fake_streamlit.reset()
        rendered_pages.clear()

    def test_logout_for_every_role_clears_auth_and_selected_page(self) -> None:
        for role in ("student", "ta", "instructor", "admin"):
            with self.subTest(role=role):
                fake_streamlit.reset()
                set_authenticated(role)
                fake_streamlit.session_state.selected_page = "Analytics"
                fake_streamlit.session_state.mock_role = "instructor"
                fake_streamlit.sidebar.logout_clicked = True

                self.assertIsNone(render_sidebar())

                self.assertEqual(
                    {
                        key: fake_streamlit.session_state[key]
                        for key in (
                            "access_token",
                            "refresh_token",
                            "current_user",
                            "role",
                            "authenticated",
                        )
                    },
                    {
                        "access_token": None,
                        "refresh_token": None,
                        "current_user": None,
                        "role": None,
                        "authenticated": False,
                    },
                )
                self.assertNotIn("selected_page", fake_streamlit.session_state)
                self.assertNotIn("mock_role", fake_streamlit.session_state)
                self.assertEqual(fake_streamlit.rerun_count, 1)

    def test_protected_content_cannot_render_after_logout(self) -> None:
        set_authenticated("instructor")
        fake_streamlit.sidebar.logout_clicked = True
        render_sidebar()

        with (
            patch.object(main, "render_login") as login_view,
            patch.object(main, "render_sidebar") as protected_navigation,
            patch.object(main, "render_page") as protected_page,
        ):
            main.main()

        login_view.assert_called_once()
        protected_navigation.assert_not_called()
        protected_page.assert_not_called()

    def test_old_instructor_analytics_does_not_leak_to_student_login(self) -> None:
        set_authenticated("instructor")
        fake_streamlit.session_state.selected_page = "Analytics"
        fake_streamlit.sidebar.logout_clicked = True
        render_sidebar()

        store_login_response(login_payload("student"))
        fake_streamlit.sidebar.logout_clicked = False
        selected_page = render_sidebar()

        self.assertEqual(selected_page, "My Attendance")
        self.assertEqual(fake_streamlit.session_state.role, "student")
        self.assertNotEqual(fake_streamlit.session_state.selected_page, "Analytics")


if __name__ == "__main__":
    unittest.main()
