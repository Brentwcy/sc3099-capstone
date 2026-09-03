"""Tests for the Week 3 TA session review page."""

from __future__ import annotations

import unittest
from contextlib import contextmanager, nullcontext
from typing import Any
from unittest.mock import MagicMock, call, patch

from tests.fakes import fake_streamlit, set_authenticated

from api_client import APIResponseError  # noqa: E402
from components.auth import authenticated_request  # noqa: E402
from pages import ta_sessions  # noqa: E402


def authorized_checkins() -> list[dict[str, Any]]:
    return [
        {
            "id": "checkin-1",
            "student_id": "student-1",
            "student_name": "Avery Student",
            "student_email": "avery@example.com",
            "status": "approved",
            "checked_in_at": "2026-09-01T09:00:00+08:00",
            "distance_from_venue_meters": 12.0,
            "risk_score": 0.1,
            "liveness_passed": True,
            "device_trusted": True,
            "risk_factors": [],
        },
        {
            "id": "checkin-2",
            "student_id": "student-2",
            "student_name": "Morgan Student",
            "student_email": "morgan@example.com",
            "status": "flagged",
            "checked_in_at": "2026-09-04T09:00:00+08:00",
            "distance_from_venue_meters": 98.0,
            "risk_score": 0.7,
            "liveness_passed": True,
            "device_trusted": False,
            "risk_factors": [{"type": "geo_out_of_bounds"}],
        },
        {
            "id": "checkin-3",
            "student_id": "student-3",
            "student_name": "Riley Student",
            "student_email": "riley@example.com",
            "status": "rejected",
            "checked_in_at": "2026-09-03T09:00:00+08:00",
            "distance_from_venue_meters": 180.0,
            "risk_score": 0.95,
            "liveness_passed": False,
            "device_trusted": False,
            "risk_factors": [{"type": "liveness_failed"}],
        },
        {
            "id": "checkin-4",
            "student_id": "student-4",
            "student_name": "Casey Student",
            "student_email": "casey@example.com",
            "status": "approved",
            "checked_in_at": "2026-09-02T09:00:00+08:00",
            "distance_from_venue_meters": 15.0,
            "risk_score": 0.05,
            "liveness_passed": True,
            "device_trusted": True,
            "risk_factors": [],
        },
    ]


class TASessionClient:
    def __init__(self, result: list[dict[str, Any]] | Exception) -> None:
        self.result = result
        self.session_calls: list[tuple[str, str]] = []
        self.general_checkin_calls = 0
        self.flagged_calls = 0

    def get_session_checkins(
        self,
        access_token: str,
        session_id: str,
    ) -> list[dict[str, Any]]:
        self.session_calls.append((access_token, session_id))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def get_checkins(self, access_token: str, **params: Any) -> dict[str, Any]:
        self.general_checkin_calls += 1
        raise AssertionError("TA page must not call the general check-in listing")

    def get_flagged_checkins(self, access_token: str) -> list[Any]:
        self.flagged_calls += 1
        raise AssertionError("The unresolved flagged endpoint must not be called")


class TASessionPageTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated("ta")
        self.session_id = ta_sessions.MOCK_SESSIONS[0]["id"]

    def test_authorized_records_drive_loading_summary_attention_and_safe_tables(self) -> None:
        records = authorized_checkins()
        client = TASessionClient(records)
        loading_events: list[str] = []

        @contextmanager
        def recording_loading(message: str):
            loading_events.append(f"enter:{message}")
            yield
            loading_events.append("exit")

        with (
            patch.object(ta_sessions.st, "caption", create=True) as caption,
            patch.object(
                ta_sessions.st,
                "columns",
                return_value=[MagicMock() for _ in range(3)],
                create=True,
            ),
            patch.object(ta_sessions.st, "button", create=True) as button,
            patch.object(
                ta_sessions,
                "loading_state",
                side_effect=recording_loading,
            ),
            patch.object(
                ta_sessions,
                "authenticated_request",
                wraps=authenticated_request,
            ) as authenticated,
            patch.object(
                ta_sessions,
                "records_to_dataframe",
                wraps=ta_sessions.records_to_dataframe,
            ) as to_dataframe,
            patch.object(
                ta_sessions,
                "convert_datetime_columns",
                wraps=ta_sessions.convert_datetime_columns,
            ) as convert_datetimes,
            patch.object(
                ta_sessions,
                "sort_dataframe",
                wraps=ta_sessions.sort_dataframe,
            ) as sort_dataframe,
            patch.object(
                ta_sessions,
                "render_session_filter",
                return_value=self.session_id,
            ) as session_filter,
            patch.object(
                ta_sessions,
                "render_status_filter",
                return_value=None,
            ),
            patch.object(ta_sessions, "render_kpi") as kpi,
            patch.object(ta_sessions, "render_table") as table,
            patch.object(ta_sessions, "render_bar_chart") as bar_chart,
        ):
            ta_sessions.render_ta_sessions(
                {"full_name": "Taylor Assistant", "role": "ta"},
                client,
            )

        authenticated.assert_called_once()
        self.assertIs(authenticated.call_args.args[0], client)
        self.assertEqual(client.session_calls, [("access-old", self.session_id)])
        self.assertEqual(loading_events, ["enter:Loading session check-ins...", "exit"])
        self.assertEqual(to_dataframe.call_count, 2)
        self.assertEqual(to_dataframe.call_args_list[1], call(records))
        self.assertEqual(convert_datetimes.call_count, 2)
        self.assertEqual(
            convert_datetimes.call_args_list[1].args[1],
            ["checked_in_at"],
        )
        self.assertEqual(sort_dataframe.call_count, 2)
        self.assertEqual(sort_dataframe.call_args_list[1].args[1], "checked_in_at")
        self.assertFalse(sort_dataframe.call_args_list[1].kwargs["ascending"])

        self.assertEqual(
            kpi.call_args_list,
            [
                call("Development Sessions", len(ta_sessions.MOCK_SESSIONS)),
                call("Session Check-ins", 4),
                call("Requiring Attention", 2),
                call("Approved", 2),
            ],
        )

        self.assertEqual(table.call_count, 4)
        session_table = table.call_args_list[0].args[0]
        attention_table = table.call_args_list[1].args[0]
        recent_table = table.call_args_list[2].args[0]
        detail_table = table.call_args_list[3].args[0]
        self.assertEqual(list(session_table.columns), ta_sessions.SESSION_COLUMNS)
        self.assertEqual(
            set(attention_table["status"]),
            ta_sessions.ATTENTION_STATUSES,
        )
        self.assertEqual(
            recent_table["student_name"].tolist(),
            [
                "Morgan Student",
                "Riley Student",
                "Casey Student",
                "Avery Student",
            ],
        )
        for checkin_table in (attention_table, recent_table, detail_table):
            self.assertEqual(list(checkin_table.columns), ta_sessions.CHECKIN_COLUMNS)
            for hidden_column in ("student_id", "device_trusted", "risk_factors"):
                self.assertNotIn(hidden_column, checkin_table.columns)

        summary = bar_chart.call_args.args[0]
        self.assertEqual(
            summary.set_index("status")["checkin_count"].to_dict(),
            {"approved": 2, "flagged": 1, "rejected": 1},
        )
        self.assertEqual(bar_chart.call_args.kwargs["x"], "status")
        self.assertEqual(bar_chart.call_args.kwargs["y"], "checkin_count")
        session_options = session_filter.call_args.args[0]
        self.assertEqual(len(session_options), len(ta_sessions.MOCK_SESSIONS))
        self.assertTrue(
            any(
                "live TA session discovery is not yet available" in item.args[0]
                for item in caption.call_args_list
            )
        )
        button.assert_not_called()
        self.assertEqual(client.general_checkin_calls, 0)
        self.assertEqual(client.flagged_calls, 0)

    def test_status_filter_applies_only_to_returned_authorized_records(self) -> None:
        client = TASessionClient(authorized_checkins())

        with (
            patch.object(ta_sessions.st, "caption", create=True),
            patch.object(
                ta_sessions.st,
                "columns",
                return_value=[MagicMock() for _ in range(3)],
                create=True,
            ),
            patch.object(ta_sessions, "loading_state", return_value=nullcontext()),
            patch.object(
                ta_sessions,
                "render_session_filter",
                return_value=self.session_id,
            ),
            patch.object(
                ta_sessions,
                "render_status_filter",
                return_value="flagged",
            ),
            patch.object(ta_sessions, "render_kpi"),
            patch.object(ta_sessions, "render_table") as table,
            patch.object(ta_sessions, "render_bar_chart"),
            patch.object(
                ta_sessions,
                "filter_equals",
                wraps=ta_sessions.filter_equals,
            ) as filter_equals,
        ):
            ta_sessions.render_ta_sessions(
                {"full_name": "Taylor Assistant", "role": "ta"},
                client,
            )

        filter_equals.assert_called_once()
        filtered = table.call_args_list[3].args[0]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["status"], "flagged")

    def test_successful_empty_live_response_uses_empty_state(self) -> None:
        client = TASessionClient([])

        with (
            patch.object(ta_sessions.st, "caption", create=True),
            patch.object(ta_sessions, "loading_state", return_value=nullcontext()),
            patch.object(
                ta_sessions,
                "render_session_filter",
                return_value=self.session_id,
            ),
            patch.object(ta_sessions, "render_kpi"),
            patch.object(ta_sessions, "render_table") as table,
            patch.object(ta_sessions, "render_empty_state") as empty_state,
            patch.object(ta_sessions, "render_bar_chart") as bar_chart,
        ):
            ta_sessions.render_ta_sessions(
                {"full_name": "Taylor Assistant", "role": "ta"},
                client,
            )

        empty_state.assert_called_once_with(
            "No check-ins were returned for this session."
        )
        self.assertEqual(table.call_count, 1)
        bar_chart.assert_not_called()

    def test_api_failure_uses_feedback_without_mock_checkin_fallback(self) -> None:
        failure = APIResponseError(status_code=403, detail="private policy detail")
        client = TASessionClient(failure)

        with (
            patch.object(ta_sessions.st, "caption", create=True),
            patch.object(ta_sessions, "loading_state", return_value=nullcontext()),
            patch.object(
                ta_sessions,
                "render_session_filter",
                return_value=self.session_id,
            ),
            patch.object(ta_sessions, "render_kpi"),
            patch.object(ta_sessions, "render_table") as table,
            patch.object(ta_sessions, "render_api_error") as api_error,
        ):
            ta_sessions.render_ta_sessions(
                {"full_name": "Taylor Assistant", "role": "ta"},
                client,
            )

        api_error.assert_called_once_with(failure)
        self.assertEqual(table.call_count, 1)
        self.assertEqual(client.general_checkin_calls, 0)
        self.assertEqual(client.flagged_calls, 0)


if __name__ == "__main__":
    unittest.main()
