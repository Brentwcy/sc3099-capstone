"""Reusable Plotly chart rendering for prepared dashboard data."""

from collections.abc import Mapping
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from components.feedback import render_empty_state


def _validate_chart_input(
    dataframe: pd.DataFrame,
    columns: tuple[str, str],
) -> bool:
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("dataframe must be a pandas DataFrame")
    if any(not isinstance(column, str) for column in columns):
        raise TypeError("chart column names must be strings")
    if dataframe.empty:
        return False

    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise KeyError(f"Missing chart columns: {missing}")
    return True


def _chart_options(
    title: str | None,
    labels: Mapping[str, str] | None,
) -> dict[str, Any]:
    if title is not None and not isinstance(title, str):
        raise TypeError("chart title must be a string or None")
    if labels is not None and not isinstance(labels, Mapping):
        raise TypeError("chart labels must be a mapping or None")

    options: dict[str, Any] = {}
    if title is not None:
        options["title"] = title
    if labels is not None:
        options["labels"] = dict(labels)
    return options


def render_line_chart(
    dataframe: pd.DataFrame,
    *,
    x: str,
    y: str,
    title: str | None = None,
    labels: Mapping[str, str] | None = None,
    empty_message: str = "No chart data found.",
) -> None:
    """Render a line chart for an already-prepared trend series."""
    chart_options = _chart_options(title, labels)
    if not _validate_chart_input(dataframe, (x, y)):
        render_empty_state(empty_message)
        return

    figure = px.line(
        data_frame=dataframe,
        x=x,
        y=y,
        **chart_options,
    )
    figure.update_layout(showlegend=False)
    st.plotly_chart(figure, use_container_width=True)


def render_bar_chart(
    dataframe: pd.DataFrame,
    *,
    x: str,
    y: str,
    title: str | None = None,
    labels: Mapping[str, str] | None = None,
    empty_message: str = "No chart data found.",
) -> None:
    """Render a zero-based bar chart for prepared category comparisons."""
    chart_options = _chart_options(title, labels)
    if not _validate_chart_input(dataframe, (x, y)):
        render_empty_state(empty_message)
        return

    figure = px.bar(
        data_frame=dataframe,
        x=x,
        y=y,
        **chart_options,
    )
    figure.update_layout(showlegend=False)
    figure.update_yaxes(rangemode="tozero")
    st.plotly_chart(figure, use_container_width=True)


def render_pie_chart(
    dataframe: pd.DataFrame,
    *,
    names: str,
    values: str,
    title: str | None = None,
    labels: Mapping[str, str] | None = None,
    hole: float = 0.0,
    empty_message: str = "No chart data found.",
) -> None:
    """Render a pie or donut chart for prepared composition data."""
    if not isinstance(hole, (int, float)) or isinstance(hole, bool):
        raise TypeError("pie chart hole must be a number")
    if not 0 <= hole < 1:
        raise ValueError("pie chart hole must be at least 0 and less than 1")
    chart_options = _chart_options(title, labels)
    if not _validate_chart_input(dataframe, (names, values)):
        render_empty_state(empty_message)
        return

    figure = px.pie(
        data_frame=dataframe,
        names=names,
        values=values,
        hole=hole,
        **chart_options,
    )
    st.plotly_chart(figure, use_container_width=True)
