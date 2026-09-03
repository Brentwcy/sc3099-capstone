"""Tests for the Week 3 Instructor Overview page."""

from __future__ import annotations

import unittest
from contextlib import contextmanager, nullcontext
from datetime import date
from typing import Any
from unittest.mock import MagicMock, call, patch

import pandas as pd

from tests.fakes import fake_streamlit, set_authenticated

from api_client import APIResponseError  # noqa: E402
from components.auth import authenticated_request  # noqa: E402
from pages import instructor_overview  # noqa: E402


def authorized_sessions() -> list[dict[str, Any]]:
    return [
        {
            "id": "session-1",
            "course_code": "SC3099",
            "course_name": "Capstone Project",
            "name": "Week 3 Studio",
            "session_type": "tutorial",
            "status": "active",
            "scheduled_start": "2026-09-03T09:00:00+08:00",
            "checkin_opens_at": "2026-09-03T08:45:00+08:00",
            "checkin_closes_at": "2026-09-03T09:30:00+08:00",
            "total_enrolled": 2,
        },
        {
            "id": "session-2",
            "course_code": "CZ3002",
            "course_name": "Advanced Software Engineering",
            "name": "Architecture Lecture",
            "session_type": "lecture",
            "status": "scheduled",
            "scheduled_start": "2026-09-03T15:00:00+08:00",
            "checkin_opens_at": "2026-09-03T14:45:00+08:00",
            "checkin_closes_at": "2026-09-03T15:30:00+08:00",
            "total_enrolled": 3,
        },
        {
            "id": "session-3",
            "course_code": "SC3099",
            "course_name": "Capstone Project",
            "name": "Week 2 Studio",
            "session_type": "tutorial",
            "status": "closed",
            "scheduled_start": "2026-09-02T09:00:00+08:00",
            "checkin_opens_at": "2026-09-02T08:45:00+08:00",
            "checkin_closes_at": "2026-09-02T09:30:00+08:00",
            "total_enrolled": 2,
        },
    ]


def authorized_checkins() -> list[dict[str, Any]]:
    return [
        {
            "id": "checkin-1",
            "session_id": "session-1",
            "session_name": "Week 3 Studio",
            "student_id": "student-1",
            "student_name": "Avery Student",
            "student_email": "avery@example.com",
            "status": "approved",
            "checked_in_at": "2026-09-03T09:00:00+08:00",
            "risk_score": 0.1,
            "liveness_passed": True,
            "device_id": "private-device-1",
            "risk_factors": [],
        },
        {
            "id": "checkin-2",
            "session_id": "session-1",
            "session_name": "Week 3 Studio",
            "student_id": "student-2",
            "student_name": "Morgan Student",
            "student_email": "morgan@example.com",
            "status": "flagged",
            "checked_in_at": "2026-09-03T09:02:00+08:00",
            "risk_score": 0.7,
            "liveness_passed": True,
            "device_id": "private-device-2",
            "risk_factors": [{"type": "geo_out_of_bounds"}],
        },
        {
            "id": "checkin-3",
            "session_id": "session-2",
            "session_name": "Architecture Lecture",
            "student_id": "student-3",
            "student_name": "Riley Student",
            "student_email": "riley@example.com",
            "status": "rejected",
            "checked_in_at": "2026-09-03T15:01:00+08:00",
            "risk_score": 0.95,
            "liveness_passed": False,
            "device_id": "private-device-3",
            "risk_factors": [{"type": "liveness_failed"}],
        },
        {
            "id": "checkin-4",
            "session_id": "session-3",
            "session_name": "Week 2 Studio",
            "student_id": "student-4",
            "student_name": "Casey Student",
            "student_email": "casey@example.com",
            "status": "approved",
            "checked_in_at": "2026-09-02T09:00:00+08:00",
            "risk_score": 0.05,
            "liveness_passed": True,
            "device_id": "private-device-4",
            "risk_factors": [],
        },
    ]


class InstructorOverviewClient:
    def __init__(
        self,
        sessions: list[dict[str, Any]] | Exception,
        checkins: list[dict[str, Any]] | Exception,
        events: list[str] | None = None,
    ) -> None:
        self.sessions = sessions
        self.checkins = checkins
        self.events = events
        self.session_calls: list[tuple[str, dict[str, Any]]] = []
        self.checkin_calls: list[tuple[str, dict[str, Any]]] = []
        self.flagged_calls = 0
        self.audit_calls = 0

    @staticmethod
    def _payload(records: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "items": records,
            "total": len(records),
            "limit": 100,
            "offset": 0,
        }

    def get_sessions(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.session_calls.append((access_token, params))
        if self.events is not None:
            self.events.append("sessions")
        if isinstance(self.sessions, Exception):
            raise self.sessions
        return self._payload(self.sessions)

    def get_checkins(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.checkin_calls.append((access_token, params))
        if self.events is not None:
            self.events.append("checkins")
        if isinstance(self.checkins, Exception):
            raise self.checkins
        return self._payload(self.checkins)

    def get_flagged_checkins(self, access_token: str) -> list[Any]:
        self.flagged_calls += 1
        raise AssertionError("The unresolved flagged endpoint must not be called")

    def get_audit_logs(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.audit_calls += 1
        raise AssertionError("Instructor Overview must not load Admin audit data")


class InstructorOverviewPageTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated("instructor")

    @staticmethod
    def columns() -> list[list[MagicMock]]:
        return [
            [MagicMock() for _ in range(3)],
            [MagicMock() for _ in range(2)],
        ]

    def test_live_data_drives_summary_tables_trend_and_safe_fields(self) -> None:
        events: list[str] = []
        sessions = authorized_sessions()
        checkins = authorized_checkins()
        client = InstructorOverviewClient(sessions, checkins, events)

        @contextmanager
        def recording_loading(message: str):
            events.append(f"enter:{message}")
            yield
            events.append("exit")

        with (
            patch.object(instructor_overview.st, "caption", create=True),
            patch.object(
                instructor_overview.st,
                "columns",
                side_effect=self.columns(),
                create=True,
            ),
            patch.object(
                instructor_overview.st,
                "expander",
                return_value=nullcontext(),
                create=True,
            ),
            patch.object(
                instructor_overview.st,
                "button",
                create=True,
            ) as button,
            patch.object(
                instructor_overview,
                "loading_state",
                side_effect=recording_loading,
            ),
            patch.object(
                instructor_overview,
                "authenticated_request",
                wraps=authenticated_request,
            ) as authenticated,
            patch.object(
                instructor_overview,
                "records_to_dataframe",
                wraps=instructor_overview.records_to_dataframe,
            ) as to_dataframe,
            patch.object(
                instructor_overview,
                "convert_datetime_columns",
                wraps=instructor_overview.convert_datetime_columns,
            ) as convert_datetimes,
            patch.object(
                instructor_overview,
                "sort_dataframe",
                wraps=instructor_overview.sort_dataframe,
            ) as sort_dataframe,
            patch.object(instructor_overview, "render_kpi") as kpi,
            patch.object(instructor_overview, "render_table") as table,
            patch.object(instructor_overview, "render_line_chart") as line_chart,
            patch.object(
                instructor_overview,
                "render_session_filter",
                return_value=None,
            ),
            patch.object(
                instructor_overview,
                "render_status_filter",
                return_value=None,
            ),
        ):
            instructor_overview.render_instructor_overview(
                {"full_name": "Indigo Instructor", "role": "instructor"},
                client,
                today=date(2026, 9, 3),
            )

        self.assertEqual(
            events,
            [
                "enter:Loading Instructor overview...",
                "sessions",
                "checkins",
                "exit",
            ],
        )
        self.assertEqual(authenticated.call_count, 2)
        self.assertTrue(all(item.args[0] is client for item in authenticated.call_args_list))
        self.assertEqual(client.session_calls, [("access-old", {"limit": 100})])
        self.assertEqual(client.checkin_calls, [("access-old", {"limit": 100})])
        self.assertEqual(to_dataframe.call_args_list, [call(sessions), call(checkins)])
        self.assertEqual(convert_datetimes.call_count, 2)
        self.assertEqual(
            convert_datetimes.call_args_list[0].args[1],
            ["scheduled_start", "checkin_opens_at", "checkin_closes_at"],
        )
        self.assertEqual(convert_datetimes.call_args_list[1].args[1], ["checked_in_at"])
        self.assertEqual(sort_dataframe.call_count, 2)

        self.assertEqual(
            kpi.call_args_list,
            [
                call("Today's Sessions", 2),
                call("Check-in Rate", "60%"),
                call("Flagged Items Requiring Action", 2),
            ],
        )

        self.assertEqual(table.call_count, 3)
        today_table = table.call_args_list[0].args[0]
        attention_table = table.call_args_list[1].args[0]
        detail_table = table.call_args_list[2].args[0]
        self.assertEqual(list(today_table.columns), instructor_overview.SESSION_COLUMNS)
        self.assertEqual(today_table["checkin_count"].tolist(), [2, 1])
        self.assertEqual(
            set(attention_table["status"]),
            instructor_overview.ATTENTION_STATUSES,
        )
        for checkin_table in (attention_table, detail_table):
            self.assertEqual(
                list(checkin_table.columns),
                instructor_overview.CHECKIN_COLUMNS,
            )
            for hidden_column in ("student_id", "device_id", "risk_factors"):
                self.assertNotIn(hidden_column, checkin_table.columns)

        trend = line_chart.call_args.args[0]
        self.assertEqual(trend["checkin_count"].tolist(), [1, 3])
        self.assertEqual(line_chart.call_args.kwargs["x"], "checkin_day")
        self.assertEqual(line_chart.call_args.kwargs["y"], "checkin_count")
        self.assertEqual(client.flagged_calls, 0)
        self.assertEqual(client.audit_calls, 0)
        button.assert_not_called()

    def test_session_and_status_filters_apply_to_detailed_records(self) -> None:
        client = InstructorOverviewClient(authorized_sessions(), authorized_checkins())

        with (
            patch.object(instructor_overview.st, "caption", create=True),
            patch.object(
                instructor_overview.st,
                "columns",
                side_effect=self.columns(),
                create=True,
            ),
            patch.object(
                instructor_overview.st,
                "expander",
                return_value=nullcontext(),
                create=True,
            ),
            patch.object(instructor_overview, "loading_state", return_value=nullcontext()),
            patch.object(instructor_overview, "render_kpi"),
            patch.object(instructor_overview, "render_table") as table,
            patch.object(instructor_overview, "render_line_chart"),
            patch.object(
                instructor_overview,
                "render_session_filter",
                return_value="session-1",
            ),
            patch.object(
                instructor_overview,
                "render_status_filter",
                return_value="flagged",
            ),
            patch.object(
                instructor_overview,
                "filter_equals",
                wraps=instructor_overview.filter_equals,
            ) as filter_equals,
        ):
            instructor_overview.render_instructor_overview(
                {"role": "instructor"},
                client,
                today=date(2026, 9, 3),
            )

        self.assertEqual(filter_equals.call_count, 2)
        filtered = table.call_args_list[2].args[0]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["session_name"], "Week 3 Studio")
        self.assertEqual(filtered.iloc[0]["status"], "flagged")

    def test_missing_or_zero_denominator_falls_back_to_count(self) -> None:
        session_checkins = pd.DataFrame([{"id": "a"}, {"id": "b"}])

        for denominator in (None, 0):
            with self.subTest(denominator=denominator):
                sessions = pd.DataFrame(
                    [{"id": "session-1", "total_enrolled": denominator}]
                )
                self.assertEqual(
                    instructor_overview._checkin_kpi(sessions, session_checkins),
                    ("Today's Check-ins", 2),
                )

    def test_successful_empty_results_use_empty_states(self) -> None:
        client = InstructorOverviewClient([], [])

        with (
            patch.object(instructor_overview.st, "caption", create=True),
            patch.object(
                instructor_overview.st,
                "columns",
                return_value=[MagicMock() for _ in range(3)],
                create=True,
            ),
            patch.object(
                instructor_overview.st,
                "expander",
                return_value=nullcontext(),
                create=True,
            ),
            patch.object(instructor_overview, "loading_state", return_value=nullcontext()),
            patch.object(instructor_overview, "render_kpi") as kpi,
            patch.object(instructor_overview, "render_table") as table,
            patch.object(instructor_overview, "render_line_chart") as line_chart,
            patch.object(instructor_overview, "render_empty_state") as empty_state,
        ):
            instructor_overview.render_instructor_overview(
                {"role": "instructor"},
                client,
                today=date(2026, 9, 3),
            )

        self.assertEqual(
            kpi.call_args_list,
            [
                call("Today's Sessions", 0),
                call("Today's Check-ins", 0),
                call("Flagged Items Requiring Action", 0),
            ],
        )
        self.assertEqual(
            empty_state.call_args_list,
            [
                call("No sessions are scheduled for today."),
                call("No flagged or rejected check-ins require attention."),
                call("No check-in records are available."),
            ],
        )
        line_chart.assert_called_once()
        self.assertTrue(line_chart.call_args.args[0].empty)
        table.assert_not_called()

    def test_api_failure_uses_safe_feedback_without_mock_fallback(self) -> None:
        failure = APIResponseError(status_code=403, detail="private policy detail")
        client = InstructorOverviewClient(failure, authorized_checkins())

        with (
            patch.object(instructor_overview.st, "caption", create=True),
            patch.object(instructor_overview, "loading_state", return_value=nullcontext()),
            patch.object(instructor_overview, "render_api_error") as api_error,
            patch.object(instructor_overview, "render_kpi") as kpi,
            patch.object(instructor_overview, "render_table") as table,
        ):
            instructor_overview.render_instructor_overview(
                {"role": "instructor"},
                client,
                today=date(2026, 9, 3),
            )

        api_error.assert_called_once_with(failure)
        kpi.assert_not_called()
        table.assert_not_called()
        self.assertEqual(client.checkin_calls, [])
        self.assertEqual(client.flagged_calls, 0)
        self.assertEqual(client.audit_calls, 0)


if __name__ == "__main__":
    unittest.main()
