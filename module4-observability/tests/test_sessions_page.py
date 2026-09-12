"""Focused tests for Week 4 role-aware session discovery and detail."""

from __future__ import annotations

import unittest
from contextlib import ExitStack, nullcontext
from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch

from tests.fakes import fake_streamlit, set_authenticated

from api_client import APIResponseError  # noqa: E402
from pages import session_forms, sessions  # noqa: E402


def confirmed_session(
    session_id: str = "session-1",
    *,
    course_id: str = "course-1",
    course_code: str = "SC3099",
) -> dict[str, Any]:
    """Return one complete response matching M2's confirmed SessionResponse."""
    return {
        "id": session_id,
        "course_id": course_id,
        "course_code": course_code,
        "course_name": "Capstone Project",
        "name": "Week 4 Studio",
        "session_type": "tutorial",
        "description": "Session discovery exercise",
        "status": "scheduled",
        "scheduled_start": "2026-09-14T09:00:00+08:00",
        "scheduled_end": "2026-09-14T10:00:00+08:00",
        "checkin_opens_at": "2026-09-14T08:45:00+08:00",
        "checkin_closes_at": "2026-09-14T09:30:00+08:00",
        "actual_start": None,
        "actual_end": None,
        "venue_latitude": 1.3,
        "venue_longitude": 103.8,
        "venue_name": "Tutorial Room 1",
        "geofence_radius_meters": 100.0,
        "require_liveness_check": True,
        "require_face_match": False,
        "risk_threshold": 0.5,
        "qr_code_enabled": False,
        "total_enrolled": 20,
        "checked_in_count": 0,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }


class SessionClient:
    def __init__(
        self,
        discovered: list[dict[str, Any]] | Exception,
        detail: dict[str, Any] | Exception | None = None,
    ) -> None:
        self.discovered = discovered
        self.detail = detail or confirmed_session()
        self.general_calls: list[tuple[str, dict[str, Any]]] = []
        self.my_calls: list[tuple[str, dict[str, Any]]] = []
        self.detail_calls: list[tuple[str, str]] = []

    def get_sessions(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.general_calls.append((access_token, params))
        if isinstance(self.discovered, Exception):
            raise self.discovered
        return {
            "items": self.discovered,
            "total": len(self.discovered),
            "limit": 100,
            "offset": 0,
        }

    def get_my_sessions(self, access_token: str, **params: Any) -> list[dict[str, Any]]:
        self.my_calls.append((access_token, params))
        if isinstance(self.discovered, Exception):
            raise self.discovered
        return self.discovered

    def get_session(self, access_token: str, session_id: str) -> dict[str, Any]:
        self.detail_calls.append((access_token, session_id))
        if isinstance(self.detail, Exception):
            raise self.detail
        return self.detail


class RoleAwareDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()

    def test_instructor_discovery_uses_general_listing_with_confirmed_filters(self) -> None:
        set_authenticated("instructor")
        records = [confirmed_session()]
        client = SessionClient(records)

        result = sessions.discover_sessions(
            client,
            "instructor",
            status="active",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )

        self.assertEqual(result, records)
        self.assertEqual(client.my_calls, [])
        self.assertEqual(
            client.general_calls,
            [
                (
                    "access-old",
                    {
                        "status": "active",
                        "start_date": "2026-09-01T00:00:00+00:00",
                        "end_date": "2026-09-30T23:59:59.999999+00:00",
                        "limit": 100,
                    },
                )
            ],
        )

    def test_admin_discovery_uses_general_listing(self) -> None:
        set_authenticated("admin")
        client = SessionClient([confirmed_session()])

        sessions.discover_sessions(client, "admin")

        self.assertEqual(len(client.general_calls), 1)
        self.assertEqual(client.my_calls, [])

    def test_ta_discovery_uses_my_sessions_and_preserves_backend_result(self) -> None:
        set_authenticated("ta")
        records = [
            confirmed_session(),
            confirmed_session(
                "session-2",
                course_id="course-2",
                course_code="CZ3002",
            ),
        ]
        client = SessionClient(records)

        result = sessions.discover_sessions(
            client,
            "ta",
            status="scheduled",
            upcoming=False,
        )

        self.assertIs(result, records)
        self.assertEqual(client.general_calls, [])
        self.assertEqual(
            client.my_calls,
            [
                (
                    "access-old",
                    {"status": "scheduled", "upcoming": False, "limit": 100},
                )
            ],
        )
        self.assertEqual(
            [record["course_id"] for record in result],
            ["course-1", "course-2"],
        )


class SessionDiscoveryPageTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated("instructor")

    def _page_patches(self, *, selected_session: str | None = "session-1"):
        return (
            patch.object(sessions.st, "subheader", create=True),
            patch.object(sessions, "render_status_filter", return_value=None),
            patch.object(
                sessions,
                "render_date_range_filter",
                return_value=(None, None),
            ),
            patch.object(
                sessions,
                "render_session_filter",
                return_value=selected_session,
            ),
            patch.object(sessions, "loading_state", return_value=nullcontext()),
        )

    def test_selection_fetches_authoritative_detail_and_renders_confirmed_fields(self) -> None:
        record = confirmed_session()
        client = SessionClient([record], detail=record)
        with ExitStack() as stack:
            for page_patch in self._page_patches():
                stack.enter_context(page_patch)
            table = stack.enter_context(patch.object(sessions, "render_table"))
            empty_state = stack.enter_context(
                patch.object(sessions, "render_empty_state")
            )
            selected = sessions.render_session_discovery("instructor", client)

        self.assertEqual(selected, "session-1")
        self.assertEqual(client.detail_calls, [("access-old", "session-1")])
        self.assertEqual(table.call_count, 2)
        self.assertEqual(
            list(table.call_args_list[0].args[0].columns),
            sessions.SESSION_LIST_COLUMNS,
        )
        detail_values = table.call_args_list[1].args[0].set_index("Field")["Value"]
        self.assertEqual(detail_values["Session"], "Week 4 Studio")
        self.assertEqual(detail_values["Liveness required"], "Yes")
        self.assertEqual(detail_values["Face match required"], "No")
        empty_state.assert_not_called()

    def test_authoritative_detail_is_passed_to_optional_renderer(self) -> None:
        record = confirmed_session()
        client = SessionClient([record], detail=record)
        with ExitStack() as stack:
            for page_patch in self._page_patches():
                stack.enter_context(page_patch)
            stack.enter_context(patch.object(sessions, "render_table"))
            detail_renderer = MagicMock()
            selected = sessions.render_session_discovery(
                "instructor",
                client,
                detail_renderer=detail_renderer,
            )

        self.assertEqual(selected, "session-1")
        detail_renderer.assert_called_once_with(record)

    def test_empty_api_result_uses_empty_state_without_detail_request(self) -> None:
        client = SessionClient([])
        with ExitStack() as stack:
            for page_patch in self._page_patches():
                stack.enter_context(page_patch)
            table = stack.enter_context(patch.object(sessions, "render_table"))
            empty_state = stack.enter_context(
                patch.object(sessions, "render_empty_state")
            )
            selected = sessions.render_session_discovery("instructor", client)

        self.assertIsNone(selected)
        empty_state.assert_called_once_with("No sessions match the selected filters.")
        table.assert_not_called()
        self.assertEqual(client.detail_calls, [])

    def test_api_failure_uses_shared_error_pattern(self) -> None:
        failure = APIResponseError(status_code=403, detail="private backend rule")
        client = SessionClient(failure)
        with ExitStack() as stack:
            for page_patch in self._page_patches():
                stack.enter_context(page_patch)
            api_error = stack.enter_context(
                patch.object(sessions, "render_api_error")
            )
            table = stack.enter_context(patch.object(sessions, "render_table"))
            selected = sessions.render_session_discovery("instructor", client)

        self.assertIsNone(selected)
        api_error.assert_called_once_with(failure)
        table.assert_not_called()
        self.assertEqual(client.detail_calls, [])

    def test_detail_api_failure_uses_shared_error_pattern(self) -> None:
        failure = APIResponseError(status_code=404, detail="private lookup detail")
        client = SessionClient([confirmed_session()], detail=failure)
        with ExitStack() as stack:
            for page_patch in self._page_patches():
                stack.enter_context(page_patch)
            api_error = stack.enter_context(
                patch.object(sessions, "render_api_error")
            )
            table = stack.enter_context(patch.object(sessions, "render_table"))
            selected = sessions.render_session_discovery("instructor", client)

        self.assertIsNone(selected)
        api_error.assert_called_once_with(failure)
        self.assertEqual(table.call_count, 1)
        self.assertEqual(client.detail_calls, [("access-old", "session-1")])

    def test_no_selection_uses_empty_state_without_detail_request(self) -> None:
        client = SessionClient([confirmed_session()])
        with ExitStack() as stack:
            for page_patch in self._page_patches(selected_session=None):
                stack.enter_context(page_patch)
            stack.enter_context(patch.object(sessions, "render_table"))
            empty_state = stack.enter_context(
                patch.object(sessions, "render_empty_state")
            )
            selected = sessions.render_session_discovery("instructor", client)

        self.assertIsNone(selected)
        empty_state.assert_called_once_with("Select a session to view its details.")
        self.assertEqual(client.detail_calls, [])


class SessionMutationVisibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()

    def test_instructor_sees_create_and_selected_detail_edit_ui(self) -> None:
        set_authenticated("instructor")
        client = SessionClient([])
        detail = confirmed_session()

        def render_discovery(role, passed_client, *, detail_renderer=None):
            self.assertEqual(role, "instructor")
            self.assertIs(passed_client, client)
            self.assertIsNotNone(detail_renderer)
            detail_renderer(detail)
            return detail["id"]

        with (
            patch.object(sessions.st, "caption", create=True),
            patch.object(
                sessions,
                "render_create_session_form",
                return_value=False,
            ) as create_form,
            patch.object(
                sessions,
                "render_session_discovery",
                side_effect=render_discovery,
            ),
            patch.object(sessions, "render_edit_session_form") as edit_form,
        ):
            sessions.render_sessions({"email": "instructor@example.com"}, client)

        create_form.assert_called_once_with(client)
        edit_form.assert_called_once_with(client, detail)

    def test_admin_has_discovery_but_no_normal_create_or_edit_ui(self) -> None:
        set_authenticated("admin")
        client = SessionClient([])
        with (
            patch.object(sessions.st, "caption", create=True),
            patch.object(sessions, "render_create_session_form") as create_form,
            patch.object(sessions, "render_edit_session_form") as edit_form,
            patch.object(sessions, "render_session_discovery") as discovery,
        ):
            sessions.render_sessions({"email": "admin@example.com"}, client)

        create_form.assert_not_called()
        edit_form.assert_not_called()
        discovery.assert_called_once_with("admin", client, detail_renderer=None)

    def test_step_four_page_has_no_lifecycle_or_delete_controls(self) -> None:
        page_source = ""
        for source in (sessions.__file__, session_forms.__file__):
            with open(source, encoding="utf-8") as page_file:
                page_source += page_file.read()

        for fragment in (
            "delete_session(",
            "Activate session",
            "Close session",
            "Cancel session",
        ):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, page_source)


if __name__ == "__main__":
    unittest.main()
