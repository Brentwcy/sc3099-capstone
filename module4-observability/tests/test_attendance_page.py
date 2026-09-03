"""Tests for the Week 3 Student My Attendance page."""

from __future__ import annotations

import unittest
from contextlib import contextmanager, nullcontext
from typing import Any
from unittest.mock import MagicMock, call, patch

import pandas as pd

from tests.fakes import fake_streamlit, set_authenticated

from api_client import APIResponseError  # noqa: E402
from components.auth import authenticated_request  # noqa: E402
from pages import student_attendance  # noqa: E402


def student_checkins() -> list[dict[str, Any]]:
    """Return own-endpoint records plus fields the page must never display."""
    return [
        {
            "id": "checkin-1",
            "session_id": "session-1",
            "session_name": "Week 1 Studio",
            "session_type": "tutorial",
            "course_code": "SC3099",
            "course_name": "Capstone Project",
            "status": "approved",
            "checked_in_at": "2026-09-01T09:00:00+08:00",
            "risk_score": 0.1,
            "student_name": "Other Student",
            "student_email": "other@example.com",
            "device_id": "private-device",
        },
        {
            "id": "checkin-2",
            "session_id": "session-2",
            "session_name": "Week 2 Studio",
            "session_type": "tutorial",
            "course_code": "SC3099",
            "course_name": "Capstone Project",
            "status": "flagged",
            "checked_in_at": "2026-09-03T09:00:00+08:00",
            "risk_score": 0.6,
        },
        {
            "id": "checkin-3",
            "session_id": "session-3",
            "session_name": "Architecture Lecture",
            "session_type": "lecture",
            "course_code": "CZ3002",
            "course_name": "Advanced Software Engineering",
            "status": "rejected",
            "checked_in_at": "2026-09-02T14:00:00+08:00",
            "risk_score": 0.9,
        },
        {
            "id": "checkin-4",
            "session_id": "session-4",
            "session_name": "Week 3 Studio",
            "session_type": "tutorial",
            "course_code": "SC3099",
            "course_name": "Capstone Project",
            "status": "approved",
            "checked_in_at": "2026-09-04T09:00:00+08:00",
            "risk_score": 0.05,
        },
    ]


class StudentCheckInClient:
    def __init__(self, result: list[dict[str, Any]] | Exception) -> None:
        self.result = result
        self.my_checkin_tokens: list[str] = []
        self.general_checkin_calls = 0
        self.my_session_calls = 0

    def get_my_checkins(self, access_token: str) -> list[dict[str, Any]]:
        self.my_checkin_tokens.append(access_token)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def get_checkins(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.general_checkin_calls += 1
        raise AssertionError("Student page must not call the general check-in listing")

    def get_my_sessions(self, access_token: str, **params: Any) -> list[Any]:
        self.my_session_calls += 1
        raise AssertionError("Relevant sessions are deferred from this page")


class StudentAttendancePageTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated("student")

    @staticmethod
    def columns() -> list[list[MagicMock]]:
        return [
            [MagicMock() for _ in range(4)],
            [MagicMock() for _ in range(2)],
        ]

    def test_own_records_drive_loading_preparation_kpis_chart_and_safe_tables(self) -> None:
        records = student_checkins()
        client = StudentCheckInClient(records)
        loading_events: list[str] = []

        @contextmanager
        def recording_loading(message: str):
            loading_events.append(f"enter:{message}")
            yield
            loading_events.append("exit")

        with (
            patch.object(
                student_attendance.st,
                "columns",
                side_effect=self.columns(),
                create=True,
            ),
            patch.object(student_attendance.st, "caption", create=True),
            patch.object(
                student_attendance,
                "loading_state",
                side_effect=recording_loading,
            ),
            patch.object(
                student_attendance,
                "authenticated_request",
                wraps=authenticated_request,
            ) as authenticated,
            patch.object(
                student_attendance,
                "records_to_dataframe",
                wraps=student_attendance.records_to_dataframe,
            ) as to_dataframe,
            patch.object(
                student_attendance,
                "convert_datetime_columns",
                wraps=student_attendance.convert_datetime_columns,
            ) as convert_datetimes,
            patch.object(
                student_attendance,
                "sort_dataframe",
                wraps=student_attendance.sort_dataframe,
            ) as sort_dataframe,
            patch.object(student_attendance, "render_kpi") as kpi,
            patch.object(student_attendance, "render_table") as table,
            patch.object(student_attendance, "render_bar_chart") as bar_chart,
            patch.object(
                student_attendance,
                "render_course_filter",
                return_value=None,
            ) as course_filter,
            patch.object(
                student_attendance,
                "render_status_filter",
                return_value=None,
            ),
        ):
            student_attendance.render_student_attendance(
                {"full_name": "Avery Student", "role": "student"},
                client,
            )

        authenticated.assert_called_once_with(client, client.get_my_checkins)
        self.assertEqual(client.my_checkin_tokens, ["access-old"])
        self.assertEqual(loading_events, ["enter:Loading your attendance...", "exit"])
        to_dataframe.assert_called_once_with(records)
        convert_datetimes.assert_called_once()
        self.assertEqual(convert_datetimes.call_args.args[1], ["checked_in_at"])
        sort_dataframe.assert_called_once()
        self.assertEqual(sort_dataframe.call_args.args[1], "checked_in_at")
        self.assertFalse(sort_dataframe.call_args.kwargs["ascending"])

        self.assertEqual(
            kpi.call_args_list,
            [
                call("Total Check-ins", 4),
                call("Approved", 2),
                call("Flagged", 1),
                call("Rejected", 1),
            ],
        )

        self.assertEqual(table.call_count, 2)
        recent = table.call_args_list[0].args[0]
        details = table.call_args_list[1].args[0]
        expected_columns = list(student_attendance.VISIBLE_CHECKIN_COLUMNS)
        self.assertEqual(list(recent.columns), expected_columns)
        self.assertEqual(list(details.columns), expected_columns)
        self.assertEqual(
            recent["session_name"].tolist(),
            [
                "Week 3 Studio",
                "Week 2 Studio",
                "Architecture Lecture",
                "Week 1 Studio",
            ],
        )
        for hidden_column in ("student_name", "student_email", "device_id", "risk_score"):
            self.assertNotIn(hidden_column, recent.columns)
            self.assertNotIn(hidden_column, details.columns)

        status_data = bar_chart.call_args.args[0]
        self.assertEqual(
            status_data.set_index("status")["count"].to_dict(),
            {"approved": 2, "flagged": 1, "rejected": 1},
        )
        self.assertEqual(bar_chart.call_args.kwargs["x"], "status")
        self.assertEqual(bar_chart.call_args.kwargs["y"], "count")

        course_options = course_filter.call_args.args[0]
        self.assertEqual(
            {option.value for option in course_options},
            {"SC3099", "CZ3002"},
        )
        self.assertEqual(client.general_checkin_calls, 0)
        self.assertEqual(client.my_session_calls, 0)

    def test_course_and_status_filters_are_applied_to_detail_rows(self) -> None:
        client = StudentCheckInClient(student_checkins())

        with (
            patch.object(
                student_attendance.st,
                "columns",
                side_effect=self.columns(),
                create=True,
            ),
            patch.object(student_attendance.st, "caption", create=True),
            patch.object(student_attendance, "loading_state", return_value=nullcontext()),
            patch.object(student_attendance, "render_kpi"),
            patch.object(student_attendance, "render_bar_chart"),
            patch.object(student_attendance, "render_table") as table,
            patch.object(
                student_attendance,
                "render_course_filter",
                return_value="SC3099",
            ),
            patch.object(
                student_attendance,
                "render_status_filter",
                return_value="approved",
            ),
            patch.object(
                student_attendance,
                "filter_equals",
                wraps=student_attendance.filter_equals,
            ) as filter_equals,
        ):
            student_attendance.render_student_attendance(
                {"full_name": "Avery Student", "role": "student"},
                client,
            )

        self.assertEqual(filter_equals.call_count, 2)
        filtered = table.call_args_list[1].args[0]
        self.assertEqual(len(filtered), 2)
        self.assertEqual(set(filtered["course_code"]), {"SC3099"})
        self.assertEqual(set(filtered["status"]), {"approved"})

    def test_successful_empty_response_uses_empty_state(self) -> None:
        client = StudentCheckInClient([])

        with (
            patch.object(student_attendance.st, "caption", create=True),
            patch.object(student_attendance, "loading_state", return_value=nullcontext()),
            patch.object(student_attendance, "render_empty_state") as empty_state,
            patch.object(student_attendance, "render_kpi") as kpi,
            patch.object(student_attendance, "render_table") as table,
            patch.object(student_attendance, "render_bar_chart") as bar_chart,
        ):
            student_attendance.render_student_attendance(
                {"full_name": "Avery Student", "role": "student"},
                client,
            )

        empty_state.assert_called_once_with("No check-ins found for your account.")
        kpi.assert_not_called()
        table.assert_not_called()
        bar_chart.assert_not_called()

    def test_api_failure_uses_safe_feedback_without_mock_fallback(self) -> None:
        failure = APIResponseError(status_code=403, detail="private backend detail")
        client = StudentCheckInClient(failure)

        with (
            patch.object(student_attendance.st, "caption", create=True),
            patch.object(student_attendance, "loading_state", return_value=nullcontext()),
            patch.object(student_attendance, "render_api_error") as api_error,
            patch.object(student_attendance, "render_table") as table,
        ):
            student_attendance.render_student_attendance(
                {"full_name": "Avery Student", "role": "student"},
                client,
            )

        api_error.assert_called_once_with(failure)
        table.assert_not_called()
        self.assertEqual(client.general_checkin_calls, 0)
        self.assertEqual(client.my_session_calls, 0)


if __name__ == "__main__":
    unittest.main()
