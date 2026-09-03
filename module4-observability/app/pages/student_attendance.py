"""Student attendance history backed by the authenticated own-data endpoint."""

from typing import Any

import pandas as pd
import streamlit as st

from api_client import APIClient, APIClientError
from components.auth import authenticated_request
from components.charts import render_bar_chart
from components.feedback import render_api_error, render_empty_state
from components.filters import FilterOption, render_course_filter, render_status_filter
from components.kpi import render_kpi
from components.loading import loading_state
from components.tables import render_table
from utils.dataframes import (
    convert_datetime_columns,
    filter_equals,
    records_to_dataframe,
    sort_dataframe,
)


REQUIRED_CHECKIN_COLUMNS = (
    "checked_in_at",
    "course_code",
    "course_name",
    "session_name",
    "session_type",
    "status",
)
VISIBLE_CHECKIN_COLUMNS = list(REQUIRED_CHECKIN_COLUMNS)
CHECKIN_COLUMN_CONFIG = {
    "checked_in_at": "Checked in",
    "course_code": "Course code",
    "course_name": "Course",
    "session_name": "Session",
    "session_type": "Session type",
    "status": "Status",
}


def _prepare_checkins(records: list[Any]) -> pd.DataFrame:
    checkins = records_to_dataframe(records)
    if checkins.empty:
        return checkins

    missing = [
        column for column in REQUIRED_CHECKIN_COLUMNS if column not in checkins.columns
    ]
    if missing:
        raise KeyError(f"Missing student check-in columns: {missing}")

    checkins = convert_datetime_columns(
        checkins,
        ["checked_in_at"],
        missing="raise",
    )
    return sort_dataframe(checkins, "checked_in_at", ascending=False)


def _course_options(checkins: pd.DataFrame) -> list[FilterOption]:
    courses = checkins[["course_code", "course_name"]].drop_duplicates()
    return [
        FilterOption(
            value=row.course_code,
            label=f"{row.course_code} — {row.course_name}",
        )
        for row in courses.itertuples(index=False)
    ]


def _status_counts(checkins: pd.DataFrame) -> pd.Series:
    return checkins["status"].value_counts()


def render_student_attendance(
    current_user: dict[str, Any],
    client: APIClient | None = None,
) -> None:
    """Render attendance data returned for the authenticated student."""
    st.title("My Attendance")
    display_name = current_user.get("full_name") or current_user.get("email") or "Student"
    st.caption(f"Check-in history for {display_name}.")

    api_client = client or APIClient()
    try:
        with loading_state("Loading your attendance..."):
            records = authenticated_request(api_client, api_client.get_my_checkins)
    except APIClientError as error:
        render_api_error(error)
        return

    try:
        checkins = _prepare_checkins(records)
    except (KeyError, TypeError, ValueError):
        render_api_error(APIClientError("Invalid student check-in response"))
        return

    if checkins.empty:
        render_empty_state("No check-ins found for your account.")
        return

    counts = _status_counts(checkins)
    metric_columns = st.columns(4)
    metrics = (
        ("Total Check-ins", len(checkins)),
        ("Approved", int(counts.get("approved", 0))),
        ("Flagged", int(counts.get("flagged", 0))),
        ("Rejected", int(counts.get("rejected", 0))),
    )
    for column, (label, value) in zip(metric_columns, metrics, strict=True):
        with column:
            render_kpi(label, value)

    st.subheader("Recent check-ins")
    render_table(
        checkins[VISIBLE_CHECKIN_COLUMNS].head(5).copy(),
        column_config=CHECKIN_COLUMN_CONFIG,
        empty_message="No recent check-ins found.",
    )

    st.subheader("Status breakdown")
    status_data = counts.rename_axis("status").reset_index(name="count")
    render_bar_chart(
        status_data,
        x="status",
        y="count",
        labels={"status": "Status", "count": "Check-ins"},
        empty_message="No status data found.",
    )

    st.subheader("Attendance details")
    filter_columns = st.columns(2)
    with filter_columns[0]:
        selected_course = render_course_filter(
            _course_options(checkins),
            key="student_attendance_course",
        )
    with filter_columns[1]:
        selected_status = render_status_filter(
            checkins["status"].dropna().astype(str).tolist(),
            key="student_attendance_status",
        )

    filtered_checkins = checkins
    if selected_course is not None:
        filtered_checkins = filter_equals(
            filtered_checkins,
            "course_code",
            selected_course,
        )
    if selected_status is not None:
        filtered_checkins = filter_equals(
            filtered_checkins,
            "status",
            selected_status,
        )

    render_table(
        filtered_checkins[VISIBLE_CHECKIN_COLUMNS],
        column_config=CHECKIN_COLUMN_CONFIG,
        empty_message="No check-ins match the selected filters.",
    )
