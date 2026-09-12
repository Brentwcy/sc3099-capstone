"""Focused tests for Week 4 Instructor session create and edit forms."""

from __future__ import annotations

import unittest
from contextlib import ExitStack, nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from tests.fakes import fake_streamlit, set_authenticated

from api_client import APIResponseError  # noqa: E402
from pages import session_forms  # noqa: E402


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def create_values(**changes: Any) -> session_forms.SessionFormValues:
    values = session_forms.SessionFormValues(
        course_id="course-1",
        name="Week 4 Studio",
        session_type="tutorial",
        description="",
        scheduled_start=utc("2026-09-20T09:00:00+08:00"),
        scheduled_end=utc("2026-09-20T10:00:00+08:00"),
        checkin_opens_at=None,
        checkin_closes_at=None,
        venue_latitude=None,
        venue_longitude=None,
        venue_name="",
        geofence_radius_meters=None,
        require_liveness_check=True,
        require_face_match=False,
        risk_threshold=None,
    )
    return replace(values, **changes)


def session_detail() -> dict[str, Any]:
    return {
        "id": "session-1",
        "course_id": "course-1",
        "name": "Week 4 Studio",
        "session_type": "tutorial",
        "description": "Existing description",
        "status": "scheduled",
        "scheduled_start": "2026-09-20T09:00:00+08:00",
        "scheduled_end": "2026-09-20T10:00:00+08:00",
        "checkin_opens_at": "2026-09-20T08:45:00+08:00",
        "checkin_closes_at": "2026-09-20T09:30:00+08:00",
        "venue_latitude": 1.3,
        "venue_longitude": 103.8,
        "venue_name": "Tutorial Room 1",
        "geofence_radius_meters": 100.0,
        "require_liveness_check": True,
        "require_face_match": False,
        "risk_threshold": 0.5,
    }


def edit_values(**changes: Any) -> session_forms.SessionFormValues:
    detail = session_detail()
    values = session_forms.SessionFormValues(
        course_id=None,
        name=detail["name"],
        session_type=detail["session_type"],
        description=detail["description"],
        scheduled_start=utc(detail["scheduled_start"]),
        scheduled_end=utc(detail["scheduled_end"]),
        checkin_opens_at=utc(detail["checkin_opens_at"]),
        checkin_closes_at=utc(detail["checkin_closes_at"]),
        venue_latitude=detail["venue_latitude"],
        venue_longitude=detail["venue_longitude"],
        venue_name=detail["venue_name"],
        geofence_radius_meters=detail["geofence_radius_meters"],
        require_liveness_check=detail["require_liveness_check"],
        require_face_match=detail["require_face_match"],
        risk_threshold=detail["risk_threshold"],
    )
    return replace(values, **changes)


class MutationClient:
    def __init__(
        self,
        *,
        create_result: dict[str, Any] | Exception | None = None,
        update_result: dict[str, Any] | Exception | None = None,
    ) -> None:
        self.create_result = create_result or session_detail()
        self.update_result = update_result or session_detail()
        self.course_calls: list[tuple[str, dict[str, Any]]] = []
        self.create_calls: list[tuple[str, dict[str, Any]]] = []
        self.update_calls: list[tuple[str, str, dict[str, Any]]] = []

    def get_courses(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.course_calls.append((access_token, params))
        return {
            "items": [
                {
                    "id": "course-1",
                    "code": "SC3099",
                    "name": "Capstone Project",
                }
            ]
        }

    def create_session(
        self,
        access_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.create_calls.append((access_token, payload))
        if isinstance(self.create_result, Exception):
            raise self.create_result
        return self.create_result

    def update_session(
        self,
        access_token: str,
        session_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.update_calls.append((access_token, session_id, payload))
        if isinstance(self.update_result, Exception):
            raise self.update_result
        return self.update_result


class SessionPayloadTests(unittest.TestCase):
    def test_create_payload_uses_confirmed_fields_and_omits_empty_optional_values(self) -> None:
        payload = session_forms.build_create_payload(create_values())

        self.assertEqual(
            payload,
            {
                "course_id": "course-1",
                "name": "Week 4 Studio",
                "session_type": "tutorial",
                "scheduled_start": "2026-09-20T01:00:00+00:00",
                "scheduled_end": "2026-09-20T02:00:00+00:00",
                "require_liveness_check": True,
                "require_face_match": False,
            },
        )
        self.assertNotIn("status", payload)

    def test_edit_payload_contains_only_changed_fields(self) -> None:
        payload = session_forms.build_update_payload(
            session_detail(),
            edit_values(name="Renamed studio", risk_threshold=0.7),
        )

        self.assertEqual(
            payload,
            {"name": "Renamed studio", "risk_threshold": 0.7},
        )
        self.assertNotIn("course_id", payload)
        self.assertNotIn("status", payload)


class SessionMutationFormTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated("instructor")
        fake_streamlit.form_submitted = True

    def _form_patches(self, values: session_forms.SessionFormValues) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(
            patch.object(session_forms, "_render_session_inputs", return_value=values)
        )
        stack.enter_context(
            patch.object(session_forms, "loading_state", return_value=nullcontext())
        )
        return stack

    def test_create_submit_calls_authenticated_wrapper_with_correct_payload(self) -> None:
        values = create_values(
            description="Hands-on session",
            venue_latitude=1.3,
            venue_longitude=103.8,
            venue_name="Tutorial Room 1",
            risk_threshold=0.4,
        )
        client = MutationClient()
        with self._form_patches(values) as stack:
            success = stack.enter_context(
                patch.object(session_forms.st, "success", create=True)
            )
            rendered = session_forms.render_create_session_form(client)

        self.assertTrue(rendered)
        self.assertEqual(
            client.course_calls,
            [("access-old", {"is_active": True, "limit": 100})],
        )
        access_token, payload = client.create_calls[0]
        self.assertEqual(access_token, "access-old")
        self.assertEqual(payload["course_id"], "course-1")
        self.assertEqual(payload["description"], "Hands-on session")
        self.assertEqual(payload["venue_latitude"], 1.3)
        self.assertEqual(payload["venue_longitude"], 103.8)
        self.assertEqual(payload["risk_threshold"], 0.4)
        self.assertNotIn("status", payload)
        success.assert_called_once_with("Session created successfully.")
        self.assertEqual(fake_streamlit.rerun_count, 1)

    def test_edit_submit_calls_update_with_only_changed_fields(self) -> None:
        client = MutationClient()
        with self._form_patches(edit_values(name="Renamed studio")) as stack:
            success = stack.enter_context(
                patch.object(session_forms.st, "success", create=True)
            )
            rendered = session_forms.render_edit_session_form(
                client,
                session_detail(),
            )

        self.assertTrue(rendered)
        self.assertEqual(
            client.update_calls,
            [("access-old", "session-1", {"name": "Renamed studio"})],
        )
        success.assert_called_once_with("Session updated successfully.")
        self.assertEqual(fake_streamlit.rerun_count, 1)

    def test_no_change_edit_does_not_call_update(self) -> None:
        client = MutationClient()
        with self._form_patches(edit_values()) as stack:
            info = stack.enter_context(
                patch.object(session_forms.st, "info", create=True)
            )
            rendered = session_forms.render_edit_session_form(
                client,
                session_detail(),
            )

        self.assertFalse(rendered)
        self.assertEqual(client.update_calls, [])
        info.assert_called_once_with("No session fields were changed.")

    def test_obvious_invalid_values_are_rejected_before_create_call(self) -> None:
        invalid_values = (
            (
                "schedule",
                create_values(
                    scheduled_end=utc("2026-09-20T08:00:00+08:00"),
                ),
                "Session end must be after session start.",
            ),
            (
                "check-in window",
                create_values(
                    checkin_opens_at=utc("2026-09-20T09:30:00+08:00"),
                    checkin_closes_at=utc("2026-09-20T09:00:00+08:00"),
                ),
                "Check-in close must be after check-in open.",
            ),
            (
                "coordinates",
                create_values(venue_latitude=1.3, venue_longitude=None),
                "Venue latitude and longitude must be provided together.",
            ),
        )
        for label, values, expected_error in invalid_values:
            with self.subTest(label=label):
                fake_streamlit.errors.clear()
                client = MutationClient()
                with self._form_patches(values):
                    rendered = session_forms.render_create_session_form(client)

                self.assertFalse(rendered)
                self.assertEqual(client.create_calls, [])
                self.assertEqual(fake_streamlit.errors, [expected_error])

    def test_create_api_failure_uses_shared_error_renderer(self) -> None:
        failure = APIResponseError(status_code=403, detail="private backend rule")
        client = MutationClient(create_result=failure)
        with self._form_patches(create_values()) as stack:
            api_error = stack.enter_context(
                patch.object(session_forms, "render_api_error")
            )
            rendered = session_forms.render_create_session_form(client)

        self.assertFalse(rendered)
        api_error.assert_called_once_with(failure)
        self.assertEqual(fake_streamlit.rerun_count, 0)

    def test_edit_api_failure_uses_shared_error_renderer(self) -> None:
        failure = APIResponseError(status_code=409, detail="private backend rule")
        client = MutationClient(update_result=failure)
        with self._form_patches(edit_values(name="Renamed studio")) as stack:
            api_error = stack.enter_context(
                patch.object(session_forms, "render_api_error")
            )
            rendered = session_forms.render_edit_session_form(
                client,
                session_detail(),
            )

        self.assertFalse(rendered)
        api_error.assert_called_once_with(failure)
        self.assertEqual(fake_streamlit.rerun_count, 0)

    def test_ta_and_admin_are_explicitly_blocked_from_both_forms(self) -> None:
        for role in ("ta", "admin"):
            with self.subTest(role=role):
                fake_streamlit.reset()
                set_authenticated(role)
                fake_streamlit.form_submitted = True
                client = MutationClient()

                create_rendered = session_forms.render_create_session_form(client)
                edit_rendered = session_forms.render_edit_session_form(
                    client,
                    session_detail(),
                )

                self.assertFalse(create_rendered)
                self.assertFalse(edit_rendered)
                self.assertEqual(client.course_calls, [])
                self.assertEqual(client.create_calls, [])
                self.assertEqual(client.update_calls, [])


if __name__ == "__main__":
    unittest.main()
