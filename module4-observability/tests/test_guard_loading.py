"""Tests for the retained page guard and reusable loading state."""

from __future__ import annotations

import unittest
from contextlib import nullcontext
from unittest.mock import patch

from tests.fakes import fake_streamlit

import pages as page_router  # noqa: E402
from components.loading import loading_state  # noqa: E402


class PageDispatchGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()

    def test_forbidden_page_requests_resolve_without_protected_content(self) -> None:
        fake_streamlit.session_state.role = "student"
        user = {"role": "student"}
        with (
            patch.object(page_router, "render_admin_overview") as admin_overview,
            patch.object(page_router, "render_instructor_overview") as instructor_overview,
            patch.object(page_router, "render_student_attendance") as attendance,
            patch.object(page_router, "render_shell") as shell,
        ):
            page_router.render_page("Overview", user)

        admin_overview.assert_not_called()
        instructor_overview.assert_not_called()
        attendance.assert_called_once_with(user)
        shell.assert_not_called()

        fake_streamlit.session_state.role = "ta"
        user = {"role": "ta"}
        with (
            patch.object(page_router, "render_admin_overview") as admin_overview,
            patch.object(page_router, "render_instructor_overview") as instructor_overview,
            patch.object(page_router, "render_student_attendance") as attendance,
            patch.object(page_router, "render_ta_sessions") as ta_sessions,
            patch.object(page_router, "render_shell") as shell,
        ):
            page_router.render_page("Exports", user)

        admin_overview.assert_not_called()
        instructor_overview.assert_not_called()
        attendance.assert_not_called()
        ta_sessions.assert_called_once_with(user)
        shell.assert_not_called()

    def test_each_role_default_dispatches_to_its_week3_implementation(self) -> None:
        cases = (
            ("student", "My Attendance", "student"),
            ("ta", "Sessions", "ta"),
            ("instructor", "Overview", "instructor"),
            ("admin", "Overview", "admin"),
        )
        for role, default_page, expected_renderer in cases:
            with self.subTest(role=role):
                fake_streamlit.session_state.role = role
                user = {"role": role}
                with (
                    patch.object(page_router, "render_student_attendance") as student,
                    patch.object(page_router, "render_ta_sessions") as ta,
                    patch.object(page_router, "render_instructor_overview") as instructor,
                    patch.object(page_router, "render_admin_overview") as admin,
                    patch.object(page_router, "render_shell") as shell,
                ):
                    page_router.render_page(default_page, user)

                renderers = {
                    "student": student,
                    "ta": ta,
                    "instructor": instructor,
                    "admin": admin,
                }
                renderers.pop(expected_renderer).assert_called_once_with(user)
                for renderer in renderers.values():
                    renderer.assert_not_called()
                shell.assert_not_called()

    def test_unknown_requests_fall_back_to_each_role_default(self) -> None:
        cases = (
            ("student", "student"),
            ("ta", "ta"),
            ("instructor", "instructor"),
            ("admin", "admin"),
        )
        for role, expected_renderer in cases:
            with self.subTest(role=role):
                fake_streamlit.session_state.role = role
                user = {"role": role}
                with (
                    patch.object(page_router, "render_student_attendance") as student,
                    patch.object(page_router, "render_ta_sessions") as ta,
                    patch.object(page_router, "render_instructor_overview") as instructor,
                    patch.object(page_router, "render_admin_overview") as admin,
                    patch.object(page_router, "render_shell") as shell,
                ):
                    page_router.render_page("Unknown Page", user)

                renderers = {
                    "student": student,
                    "ta": ta,
                    "instructor": instructor,
                    "admin": admin,
                }
                renderers.pop(expected_renderer).assert_called_once_with(user)
                for renderer in renderers.values():
                    renderer.assert_not_called()
                shell.assert_not_called()

    def test_allowed_unfinished_pages_render_safe_shells(self) -> None:
        cases = (
            ("student", "Sessions"),
            ("ta", "Check-ins"),
            ("ta", "Flagged Review"),
            ("instructor", "Sessions"),
            ("instructor", "Check-ins"),
            ("instructor", "Flagged Review"),
            ("instructor", "Analytics"),
            ("instructor", "Exports"),
            ("admin", "Audit Logs"),
            ("admin", "System Metrics"),
        )
        for role, page_name in cases:
            with self.subTest(role=role, page_name=page_name):
                fake_streamlit.session_state.role = role
                with (
                    patch.object(page_router, "render_student_attendance") as student,
                    patch.object(page_router, "render_ta_sessions") as ta,
                    patch.object(page_router, "render_instructor_overview") as instructor,
                    patch.object(page_router, "render_admin_overview") as admin,
                    patch.object(page_router, "render_shell") as shell,
                ):
                    page_router.render_page(page_name, {"role": role})

                student.assert_not_called()
                ta.assert_not_called()
                instructor.assert_not_called()
                admin.assert_not_called()
                shell.assert_called_once_with(page_name, role)

    def test_unknown_role_cannot_render_any_page(self) -> None:
        fake_streamlit.session_state.role = "unknown"

        with (
            patch.object(page_router, "render_admin_overview") as admin_overview,
            patch.object(page_router, "render_instructor_overview") as instructor_overview,
            patch.object(page_router, "render_student_attendance") as attendance,
            patch.object(page_router, "render_ta_sessions") as ta_sessions,
            patch.object(page_router, "render_shell") as shell,
            patch.object(fake_streamlit, "error") as error,
        ):
            page_router.render_page("Overview", {"role": "unknown"})

        admin_overview.assert_not_called()
        instructor_overview.assert_not_called()
        attendance.assert_not_called()
        ta_sessions.assert_not_called()
        shell.assert_not_called()
        error.assert_called_once_with(
            "No dashboard pages are available for this account."
        )

    def test_admin_destinations_are_guarded_from_student_and_ta(self) -> None:
        for role, requested_page in (
            ("student", "Audit Logs"),
            ("student", "System Metrics"),
            ("ta", "Audit Logs"),
            ("ta", "System Metrics"),
        ):
            with self.subTest(role=role, requested_page=requested_page):
                fake_streamlit.session_state.role = role
                user = {"role": role}
                with (
                    patch.object(page_router, "render_admin_overview") as admin,
                    patch.object(page_router, "render_student_attendance") as student,
                    patch.object(page_router, "render_ta_sessions") as ta,
                    patch.object(page_router, "render_shell") as shell,
                ):
                    page_router.render_page(requested_page, user)

                admin.assert_not_called()
                shell.assert_not_called()
                if role == "student":
                    student.assert_called_once_with(user)
                    ta.assert_not_called()
                else:
                    student.assert_not_called()
                    ta.assert_called_once_with(user)

    def test_role_specific_overview_routes_remain_isolated(self) -> None:
        fake_streamlit.session_state.role = "instructor"
        user = {"role": "instructor"}
        with (
            patch.object(page_router, "render_instructor_overview") as instructor,
            patch.object(page_router, "render_admin_overview") as admin,
        ):
            page_router.render_page("Overview", user)

        instructor.assert_called_once_with(user)
        admin.assert_not_called()

        fake_streamlit.session_state.role = "admin"
        user = {"role": "admin"}
        with (
            patch.object(page_router, "render_instructor_overview") as instructor,
            patch.object(page_router, "render_admin_overview") as admin,
        ):
            page_router.render_page("Overview", user)

        instructor.assert_not_called()
        admin.assert_called_once_with(user)


class LoadingStateTests(unittest.TestCase):
    def test_loading_state_wraps_work_without_changing_session_state(self) -> None:
        events: list[str] = []
        fake_streamlit.session_state.update(
            {"authenticated": True, "access_token": "access-token"}
        )
        original_state = dict(fake_streamlit.session_state)

        class RecordingSpinner:
            def __enter__(self) -> None:
                events.append("spinner-enter")

            def __exit__(self, *args: object) -> bool:
                events.append("spinner-exit")
                return False

        with patch.object(
            fake_streamlit,
            "spinner",
            return_value=RecordingSpinner(),
            create=True,
        ) as spinner:
            with loading_state("Loading sessions..."):
                events.append("work")

        spinner.assert_called_once_with("Loading sessions...")
        self.assertEqual(events, ["spinner-enter", "work", "spinner-exit"])
        self.assertEqual(dict(fake_streamlit.session_state), original_state)

    def test_loading_state_does_not_hide_errors(self) -> None:
        with patch.object(
            fake_streamlit,
            "spinner",
            return_value=nullcontext(),
            create=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "backend failure"):
                with loading_state("Loading check-ins..."):
                    raise RuntimeError("backend failure")

    def test_loading_state_rejects_an_empty_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            with loading_state("  "):
                pass


if __name__ == "__main__":
    unittest.main()
