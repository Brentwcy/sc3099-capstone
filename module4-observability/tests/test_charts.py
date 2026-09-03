"""Tests for reusable Week 3 Plotly chart components."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from tests.fakes import fake_streamlit

from components import charts  # noqa: E402


class ChartRenderingTests(unittest.TestCase):
    def test_line_chart_uses_expected_series_title_and_labels(self) -> None:
        dataframe = pd.DataFrame(
            [{"date": "2026-09-01", "attendance": 42}]
        )
        figure = MagicMock()

        with (
            patch.object(charts.px, "line", return_value=figure) as line,
            patch.object(fake_streamlit, "plotly_chart", create=True) as plotly_chart,
        ):
            charts.render_line_chart(
                dataframe,
                x="date",
                y="attendance",
                title="Attendance trend",
                labels={"date": "Date", "attendance": "Attendance"},
            )

        line.assert_called_once_with(
            data_frame=dataframe,
            x="date",
            y="attendance",
            title="Attendance trend",
            labels={"date": "Date", "attendance": "Attendance"},
        )
        figure.update_layout.assert_called_once_with(showlegend=False)
        plotly_chart.assert_called_once_with(figure, use_container_width=True)

    def test_bar_chart_uses_categories_values_and_zero_baseline(self) -> None:
        dataframe = pd.DataFrame(
            [
                {"status": "approved", "count": 8},
                {"status": "flagged", "count": 2},
            ]
        )
        figure = MagicMock()

        with (
            patch.object(charts.px, "bar", return_value=figure) as bar,
            patch.object(fake_streamlit, "plotly_chart", create=True) as plotly_chart,
        ):
            charts.render_bar_chart(dataframe, x="status", y="count")

        bar.assert_called_once_with(data_frame=dataframe, x="status", y="count")
        figure.update_layout.assert_called_once_with(showlegend=False)
        figure.update_yaxes.assert_called_once_with(rangemode="tozero")
        plotly_chart.assert_called_once_with(figure, use_container_width=True)

    def test_pie_chart_accepts_composition_data_and_donut_hole(self) -> None:
        dataframe = pd.DataFrame(
            [
                {"status": "approved", "count": 8},
                {"status": "flagged", "count": 2},
            ]
        )
        figure = MagicMock()

        with (
            patch.object(charts.px, "pie", return_value=figure) as pie,
            patch.object(fake_streamlit, "plotly_chart", create=True) as plotly_chart,
        ):
            charts.render_pie_chart(
                dataframe,
                names="status",
                values="count",
                title="Check-in composition",
                hole=0.4,
            )

        pie.assert_called_once_with(
            data_frame=dataframe,
            names="status",
            values="count",
            hole=0.4,
            title="Check-in composition",
        )
        plotly_chart.assert_called_once_with(figure, use_container_width=True)

    def test_empty_data_uses_shared_empty_state_without_plotly(self) -> None:
        renderers = (
            (charts.render_line_chart, {"x": "date", "y": "count"}, "line"),
            (charts.render_bar_chart, {"x": "status", "y": "count"}, "bar"),
            (
                charts.render_pie_chart,
                {"names": "status", "values": "count"},
                "pie",
            ),
        )

        for renderer, arguments, plotly_method in renderers:
            with self.subTest(renderer=renderer.__name__):
                with (
                    patch.object(charts, "render_empty_state") as empty_state,
                    patch.object(charts.px, plotly_method) as plotly_builder,
                    patch.object(
                        fake_streamlit,
                        "plotly_chart",
                        create=True,
                    ) as plotly_chart,
                ):
                    renderer(
                        pd.DataFrame(),
                        empty_message="No trend data found.",
                        **arguments,
                    )

                empty_state.assert_called_once_with("No trend data found.")
                plotly_builder.assert_not_called()
                plotly_chart.assert_not_called()

    def test_missing_columns_and_non_dataframe_inputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(KeyError, "missing"):
            charts.render_line_chart(
                pd.DataFrame([{"date": "2026-09-01"}]),
                x="date",
                y="missing",
            )
        with self.assertRaisesRegex(TypeError, "pandas DataFrame"):
            charts.render_bar_chart(None, x="status", y="count")  # type: ignore[arg-type]

    def test_invalid_donut_hole_is_rejected(self) -> None:
        dataframe = pd.DataFrame([{"status": "approved", "count": 1}])

        with self.assertRaisesRegex(ValueError, "less than 1"):
            charts.render_pie_chart(
                dataframe,
                names="status",
                values="count",
                hole=1.0,
            )


if __name__ == "__main__":
    unittest.main()
