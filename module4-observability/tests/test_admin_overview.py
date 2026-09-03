"""Tests for the Week 3 Admin Overview page."""

from __future__ import annotations

import unittest
from contextlib import contextmanager, nullcontext
from typing import Any
from unittest.mock import MagicMock, call, patch

from tests.fakes import fake_streamlit, set_authenticated

from api_client import APIClientError, APIResponseError  # noqa: E402
from components.auth import authenticated_request  # noqa: E402
from pages import admin_overview  # noqa: E402


def course_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active = [
        {
            "id": "course-1",
            "code": "SC3099",
            "name": "Capstone Project",
            "semester": "AY26/27 S1",
            "is_active": True,
            "venue_name": "Innovation Lab",
            "risk_threshold": 0.5,
        },
        {
            "id": "course-2",
            "code": "CZ3002",
            "name": "Advanced Software Engineering",
            "semester": "AY26/27 S1",
            "is_active": True,
            "venue_name": None,
            "risk_threshold": 0.6,
        },
    ]
    inactive = [
        {
            "id": "course-3",
            "code": "CZ2006",
            "name": "Software Engineering",
            "semester": "AY25/26 S2",
            "is_active": False,
            "venue_name": "Lecture Theatre 1",
            "risk_threshold": 0.5,
        }
    ]
    return active, inactive


def checkin_records() -> list[dict[str, Any]]:
    return [
        {
            "id": "checkin-1",
            "session_name": "Week 3 Studio",
            "student_id": "student-1",
            "student_name": "Avery Student",
            "student_email": "avery@example.com",
            "status": "approved",
            "checked_in_at": "2026-09-03T09:00:00+08:00",
            "device_id": "private-device-1",
            "risk_score": 0.1,
            "risk_factors": [],
        },
        {
            "id": "checkin-2",
            "session_name": "Week 3 Studio",
            "student_id": "student-2",
            "student_name": "Morgan Student",
            "student_email": "morgan@example.com",
            "status": "flagged",
            "checked_in_at": "2026-09-03T09:02:00+08:00",
            "device_id": "private-device-2",
            "risk_score": 0.8,
            "risk_factors": [{"type": "geo_out_of_bounds"}],
        },
        {
            "id": "checkin-3",
            "session_name": "Architecture Lecture",
            "student_id": "student-3",
            "student_name": "Riley Student",
            "student_email": "riley@example.com",
            "status": "approved",
            "checked_in_at": "2026-09-02T15:00:00+08:00",
            "device_id": "private-device-3",
            "risk_score": 0.05,
            "risk_factors": [],
        },
    ]


def audit_records() -> list[dict[str, Any]]:
    return [
        {
            "id": "audit-1",
            "timestamp": "2026-09-03T10:00:00+08:00",
            "user_email": "admin@example.com",
            "action": "course_updated",
            "resource_type": "course",
            "success": True,
            "ip_address": "192.0.2.10",
            "user_agent": "private-agent",
            "device_id": "private-device",
            "details": {"changed_fields": ["name"]},
        },
        {
            "id": "audit-2",
            "timestamp": "2026-09-03T09:00:00+08:00",
            "user_email": None,
            "action": "checkin_attempted",
            "resource_type": "session",
            "success": False,
            "ip_address": "192.0.2.11",
            "user_agent": "private-agent",
            "device_id": "private-device",
            "details": {"latitude": 1.0},
        },
    ]


class AdminOverviewClient:
    def __init__(
        self,
        active: list[dict[str, Any]] | Exception,
        inactive: list[dict[str, Any]],
        checkins: list[dict[str, Any]],
        audits: list[dict[str, Any]],
        events: list[str] | None = None,
    ) -> None:
        self.active = active
        self.inactive = inactive
        self.checkins = checkins
        self.audits = audits
        self.events = events
        self.course_calls: list[tuple[str, dict[str, Any]]] = []
        self.checkin_calls: list[tuple[str, dict[str, Any]]] = []
        self.audit_calls: list[tuple[str, dict[str, Any]]] = []
        self.health_calls = 0

    @staticmethod
    def _payload(records: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "items": records,
            "total": len(records),
            "limit": 100,
            "offset": 0,
        }

    def get_courses(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.course_calls.append((access_token, params))
        active = params["is_active"]
        if self.events is not None:
            self.events.append(f"courses:{active}")
        if active and isinstance(self.active, Exception):
            raise self.active
        records = self.active if active else self.inactive
        return self._payload(records)  # type: ignore[arg-type]

    def get_checkins(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.checkin_calls.append((access_token, params))
        if self.events is not None:
            self.events.append("checkins")
        return self._payload(self.checkins)

    def get_audit_logs(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.audit_calls.append((access_token, params))
        if self.events is not None:
            self.events.append("audit")
        return self._payload(self.audits)

    def check_health(self) -> dict[str, Any]:
        self.health_calls += 1
        if self.events is not None:
            self.events.append("health")
        return {
            "reachable": True,
            "healthy": True,
            "status_code": 200,
            "data": {"status": "healthy"},
        }


class AdminOverviewPageTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated("admin")

    def make_client(self, events: list[str] | None = None) -> AdminOverviewClient:
        active, inactive = course_records()
        return AdminOverviewClient(
            active,
            inactive,
            checkin_records(),
            audit_records(),
            events,
        )

    def test_paginated_contract_preserves_backend_total(self) -> None:
        records = [{"id": "course-1"}]

        items, total = admin_overview._paginated_data(
            {
                "items": records,
                "total": 17,
                "limit": 1,
                "offset": 0,
            },
            "course",
        )

        self.assertIs(items, records)
        self.assertEqual(total, 17)

        with self.assertRaisesRegex(APIClientError, "Invalid course response"):
            admin_overview._paginated_data(
                {"items": records, "total": "17"},
                "course",
            )

    def test_live_sources_drive_kpis_safe_tables_chart_and_destinations(self) -> None:
        events: list[str] = []
        client = self.make_client(events)

        @contextmanager
        def recording_loading(message: str):
            events.append(f"enter:{message}")
            yield
            events.append("exit")

        with (
            patch.object(admin_overview.st, "caption", create=True) as caption,
            patch.object(
                admin_overview.st,
                "columns",
                return_value=[MagicMock() for _ in range(4)],
                create=True,
            ),
            patch.object(
                admin_overview.st,
                "expander",
                return_value=nullcontext(),
                create=True,
            ),
            patch.object(admin_overview.st, "markdown", create=True) as markdown,
            patch.object(
                admin_overview,
                "loading_state",
                side_effect=recording_loading,
            ),
            patch.object(
                admin_overview,
                "authenticated_request",
                wraps=authenticated_request,
            ) as authenticated,
            patch.object(
                admin_overview,
                "records_to_dataframe",
                wraps=admin_overview.records_to_dataframe,
            ) as to_dataframe,
            patch.object(
                admin_overview,
                "sort_dataframe",
                wraps=admin_overview.sort_dataframe,
            ) as sort_dataframe,
            patch.object(admin_overview, "render_kpi") as kpi,
            patch.object(admin_overview, "render_table") as table,
            patch.object(admin_overview, "render_bar_chart") as bar_chart,
            patch.object(admin_overview, "render_status_filter", return_value=None),
        ):
            admin_overview.render_admin_overview(
                {"full_name": "Ari Admin", "role": "admin"},
                client,
            )

        self.assertEqual(
            events,
            [
                "enter:Loading Admin overview...",
                "courses:True",
                "courses:False",
                "checkins",
                "audit",
                "health",
                "exit",
            ],
        )
        self.assertEqual(authenticated.call_count, 4)
        self.assertTrue(all(item.args[0] is client for item in authenticated.call_args_list))
        self.assertEqual(
            client.course_calls,
            [
                ("access-old", {"is_active": True, "limit": 100}),
                ("access-old", {"is_active": False, "limit": 100}),
            ],
        )
        self.assertEqual(client.checkin_calls, [("access-old", {"limit": 100})])
        self.assertEqual(client.audit_calls, [("access-old", {"limit": 20})])
        self.assertEqual(client.health_calls, 1)
        self.assertEqual(to_dataframe.call_count, 3)
        self.assertGreaterEqual(sort_dataframe.call_count, 4)
        self.assertEqual(
            kpi.call_args_list,
            [
                call("Total Courses", 3),
                call("Active Courses", 2),
                call("Recent Check-ins", 3),
                call("Recent Audit Events", 2),
            ],
        )

        self.assertEqual(table.call_count, 3)
        courses = table.call_args_list[0].args[0]
        audits = table.call_args_list[1].args[0]
        checkins = table.call_args_list[2].args[0]
        self.assertEqual(list(courses.columns), admin_overview.COURSE_COLUMNS)
        self.assertEqual(courses.loc[courses["code"] == "CZ3002", "venue_name"].iat[0], "Not specified")
        self.assertEqual(list(audits.columns), admin_overview.AUDIT_COLUMNS)
        self.assertEqual(audits.loc[audits["action"] == "checkin_attempted", "user_email"].iat[0], "System")
        for hidden_column in ("ip_address", "user_agent", "device_id", "details"):
            self.assertNotIn(hidden_column, audits.columns)
        self.assertEqual(list(checkins.columns), admin_overview.CHECKIN_COLUMNS)
        for hidden_column in ("student_id", "device_id", "risk_score", "risk_factors"):
            self.assertNotIn(hidden_column, checkins.columns)

        summary = bar_chart.call_args.args[0]
        self.assertEqual(
            summary.set_index("status")["checkin_count"].to_dict(),
            {"approved": 2, "flagged": 1},
        )
        self.assertEqual(bar_chart.call_args.kwargs["x"], "status")
        self.assertEqual(bar_chart.call_args.kwargs["y"], "checkin_count")
        self.assertIn("Audit Logs", markdown.call_args.args[0])
        self.assertIn("System Metrics", markdown.call_args.args[0])
        self.assertTrue(
            any("API status: Healthy" in item.args[0] for item in caption.call_args_list)
        )

    def test_status_filter_applies_to_recent_checkin_details(self) -> None:
        client = self.make_client()

        with (
            patch.object(admin_overview.st, "caption", create=True),
            patch.object(
                admin_overview.st,
                "columns",
                return_value=[MagicMock() for _ in range(4)],
                create=True,
            ),
            patch.object(
                admin_overview.st,
                "expander",
                return_value=nullcontext(),
                create=True,
            ),
            patch.object(admin_overview.st, "markdown", create=True),
            patch.object(admin_overview, "loading_state", return_value=nullcontext()),
            patch.object(admin_overview, "render_kpi"),
            patch.object(admin_overview, "render_table") as table,
            patch.object(admin_overview, "render_bar_chart"),
            patch.object(
                admin_overview,
                "render_status_filter",
                return_value="flagged",
            ),
            patch.object(
                admin_overview,
                "filter_equals",
                wraps=admin_overview.filter_equals,
            ) as filter_equals,
        ):
            admin_overview.render_admin_overview({"role": "admin"}, client)

        self.assertEqual(filter_equals.call_count, 2)
        filtered = table.call_args_list[2].args[0]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["status"], "flagged")

    def test_successful_empty_responses_use_empty_states(self) -> None:
        client = AdminOverviewClient([], [], [], [])

        with (
            patch.object(admin_overview.st, "caption", create=True),
            patch.object(
                admin_overview.st,
                "columns",
                return_value=[MagicMock() for _ in range(4)],
                create=True,
            ),
            patch.object(
                admin_overview.st,
                "expander",
                return_value=nullcontext(),
                create=True,
            ),
            patch.object(admin_overview.st, "markdown", create=True),
            patch.object(admin_overview, "loading_state", return_value=nullcontext()),
            patch.object(admin_overview, "render_kpi") as kpi,
            patch.object(admin_overview, "render_table") as table,
            patch.object(admin_overview, "render_bar_chart") as bar_chart,
            patch.object(admin_overview, "render_empty_state") as empty_state,
        ):
            admin_overview.render_admin_overview({"role": "admin"}, client)

        self.assertEqual(
            kpi.call_args_list,
            [
                call("Total Courses", 0),
                call("Active Courses", 0),
                call("Recent Check-ins", 0),
                call("Recent Audit Events", 0),
            ],
        )
        self.assertEqual(
            empty_state.call_args_list,
            [
                call("No courses were returned for this account."),
                call("No recent check-in activity was returned."),
                call("No recent audit events were returned."),
                call("No recent check-in records are available."),
            ],
        )
        table.assert_not_called()
        bar_chart.assert_not_called()

    def test_api_failure_uses_safe_feedback_without_mock_fallback(self) -> None:
        failure = APIResponseError(status_code=403, detail="private policy detail")
        client = AdminOverviewClient(failure, [], [], [])

        with (
            patch.object(admin_overview.st, "caption", create=True),
            patch.object(admin_overview, "loading_state", return_value=nullcontext()),
            patch.object(admin_overview, "render_api_error") as api_error,
            patch.object(admin_overview, "render_kpi") as kpi,
            patch.object(admin_overview, "render_table") as table,
        ):
            admin_overview.render_admin_overview({"role": "admin"}, client)

        api_error.assert_called_once_with(failure)
        kpi.assert_not_called()
        table.assert_not_called()
        self.assertEqual(client.checkin_calls, [])
        self.assertEqual(client.audit_calls, [])
        self.assertEqual(client.health_calls, 0)


if __name__ == "__main__":
    unittest.main()
