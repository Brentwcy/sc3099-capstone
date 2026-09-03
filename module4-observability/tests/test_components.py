"""Focused tests for reusable Week 3 dashboard components."""

from __future__ import annotations

import sys
import unittest
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

from tests.fakes import fake_streamlit

try:
    import pandas as pd
except ModuleNotFoundError:
    class FakeDataFrame:
        """Small DataFrame stand-in for dependency-light unit test runs."""

        def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
            self.records = records or []
            self.columns = list(self.records[0]) if self.records else []

        @property
        def empty(self) -> bool:
            return not self.records

        def __getitem__(self, columns: list[str]) -> FakeDataFrame:
            return FakeDataFrame(
                [{column: record[column] for column in columns} for record in self.records]
            )

        def __len__(self) -> int:
            return len(self.records)

    pd = ModuleType("pandas")
    pd.DataFrame = FakeDataFrame  # type: ignore[attr-defined]
    sys.modules["pandas"] = pd

from api_client import (  # noqa: E402
    APIClientError,
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
)
from components.feedback import render_api_error, render_empty_state  # noqa: E402
from components.kpi import render_kpi  # noqa: E402
from components import tables  # noqa: E402
from pages import overview  # noqa: E402


class KPIComponentTests(unittest.TestCase):
    def test_required_values_are_passed_to_streamlit_metric(self) -> None:
        with patch.object(fake_streamlit, "metric", create=True) as metric:
            render_kpi("Active sessions", 7)

        metric.assert_called_once_with(label="Active sessions", value=7)

    def test_optional_delta_and_help_are_passed_when_present(self) -> None:
        with patch.object(fake_streamlit, "metric", create=True) as metric:
            render_kpi(
                "Approval rate",
                "92%",
                delta="3%",
                help_text="Compared with last week",
            )

        metric.assert_called_once_with(
            label="Approval rate",
            value="92%",
            delta="3%",
            help="Compared with last week",
        )


class FeedbackComponentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_session_state = dict(fake_streamlit.session_state)

    def tearDown(self) -> None:
        fake_streamlit.session_state.clear()
        fake_streamlit.session_state.update(self.original_session_state)

    def test_empty_state_renders_the_supplied_message(self) -> None:
        with patch.object(fake_streamlit, "info", create=True) as info:
            render_empty_state("No recent check-ins found.")

        info.assert_called_once_with("No recent check-ins found.")

    def test_timeout_and_connection_errors_have_safe_messages(self) -> None:
        failures = (
            (APITimeoutError("private timeout details"), "timed out"),
            (APIConnectionError("private host details"), "currently unavailable"),
        )

        for error, expected_text in failures:
            with self.subTest(error=type(error).__name__):
                with patch.object(fake_streamlit, "error") as display_error:
                    render_api_error(error)

                message = display_error.call_args.args[0]
                self.assertIn(expected_text, message)
                self.assertNotIn("private", message)

    def test_permission_error_maps_to_permission_message(self) -> None:
        error = APIResponseError(status_code=403, detail="sensitive policy details")

        with patch.object(fake_streamlit, "error") as display_error:
            render_api_error(error)

        display_error.assert_called_once_with(
            "You do not have permission to perform this action."
        )

    def test_rate_limit_error_maps_to_try_again_message(self) -> None:
        error = APIResponseError(
            status_code=429,
            detail="sensitive limiter details",
            retry_after="30",
        )

        with patch.object(fake_streamlit, "warning", create=True) as warning:
            render_api_error(error)

        warning.assert_called_once_with("Too many requests. Please try again later.")

    def test_generic_api_errors_do_not_expose_internal_details(self) -> None:
        errors = (
            APIResponseError(status_code=500, detail="database-password=secret"),
            APIClientError("internal-host.example"),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch.object(fake_streamlit, "error") as display_error:
                    render_api_error(error)

                message = display_error.call_args.args[0]
                self.assertNotIn("secret", message)
                self.assertNotIn("internal-host", message)

    def test_rendering_an_error_does_not_change_authentication_state(self) -> None:
        fake_streamlit.session_state.update(
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "authenticated": True,
            }
        )
        original_state = dict(fake_streamlit.session_state)

        with patch.object(fake_streamlit, "error"):
            render_api_error(APIResponseError(status_code=403, detail="forbidden"))

        self.assertEqual(dict(fake_streamlit.session_state), original_state)


class TableComponentTests(unittest.TestCase):
    def test_non_empty_dataframe_uses_full_width_and_hides_index(self) -> None:
        dataframe = pd.DataFrame([{"status": "approved"}])

        with patch.object(fake_streamlit, "dataframe", create=True) as dataframe_ui:
            tables.render_table(dataframe)

        self.assertIs(dataframe_ui.call_args.args[0], dataframe)
        self.assertEqual(
            dataframe_ui.call_args.kwargs,
            {"hide_index": True, "use_container_width": True},
        )

    def test_column_config_and_height_are_passed_through(self) -> None:
        dataframe = pd.DataFrame([{"risk_score": 0.25}])
        column_config = {"risk_score": "Risk score"}

        with patch.object(fake_streamlit, "dataframe", create=True) as dataframe_ui:
            tables.render_table(
                dataframe,
                column_config=column_config,
                height=320,
            )

        self.assertIs(dataframe_ui.call_args.args[0], dataframe)
        self.assertEqual(
            dataframe_ui.call_args.kwargs,
            {
                "hide_index": True,
                "use_container_width": True,
                "column_config": column_config,
                "height": 320,
            },
        )

    def test_empty_dataframe_uses_shared_empty_state_only(self) -> None:
        with (
            patch.object(tables, "render_empty_state") as empty_state,
            patch.object(fake_streamlit, "dataframe", create=True) as dataframe_ui,
        ):
            tables.render_table(
                pd.DataFrame(),
                empty_message="No recent check-ins found.",
            )

        empty_state.assert_called_once_with("No recent check-ins found.")
        dataframe_ui.assert_not_called()

    def test_none_is_rejected_as_a_programmer_error(self) -> None:
        with self.assertRaisesRegex(TypeError, "pandas DataFrame"):
            tables.render_table(None)  # type: ignore[arg-type]


class OverviewCompatibilityTests(unittest.TestCase):
    def test_legacy_overview_entry_delegates_to_admin_overview(self) -> None:
        user = {"full_name": "Test Admin", "role": "admin"}

        with patch.object(overview, "render_admin_overview") as admin_overview:
            overview.render_overview(user)

        admin_overview.assert_called_once_with(user)


if __name__ == "__main__":
    unittest.main()
