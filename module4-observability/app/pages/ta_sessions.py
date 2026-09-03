"""TA session review backed by backend-authorized session check-ins."""

from typing import Any

import pandas as pd
import streamlit as st

from api_client import APIClient, APIClientError
from components.auth import authenticated_request
from components.charts import render_bar_chart
from components.feedback import render_api_error, render_empty_state
from components.filters import FilterOption, render_session_filter, render_status_filter
from components.kpi import render_kpi
from components.loading import loading_state
from components.tables import render_table
from utils.dataframes import (
    convert_datetime_columns,
    filter_equals,
    records_to_dataframe,
    sort_dataframe,
)
from utils.mock_data import MOCK_SESSIONS


SESSION_COLUMNS = [
    "scheduled_start",
    "course_code",
    "course_name",
    "name",
    "session_type",
    "status",
    "venue_name",
]
SESSION_COLUMN_CONFIG = {
    "scheduled_start": "Scheduled start",
    "course_code": "Course code",
    "course_name": "Course",
    "name": "Session",
    "session_type": "Session type",
    "status": "Status",
    "venue_name": "Venue",
}
CHECKIN_COLUMNS = [
    "checked_in_at",
    "student_name",
    "student_email",
    "status",
    "distance_from_venue_meters",
    "risk_score",
    "liveness_passed",
]
CHECKIN_COLUMN_CONFIG = {
    "checked_in_at": "Checked in",
    "student_name": "Student",
    "student_email": "Email",
    "status": "Status",
    "distance_from_venue_meters": "Distance from venue (m)",
    "risk_score": "Risk score",
    "liveness_passed": "Liveness passed",
}
ATTENTION_STATUSES = frozenset({"flagged", "rejected"})
TA_SESSION_SOURCE_MESSAGE = (
    "Development session list — live TA session discovery is not yet available. "
    "Selecting a session sends a live backend-authorized check-in request."
)


def get_ta_session_options() -> pd.DataFrame:
    """Return the replaceable development source for TA session discovery."""
    sessions = records_to_dataframe(MOCK_SESSIONS)
    sessions = convert_datetime_columns(
        sessions,
        ["scheduled_start"],
        missing="raise",
    )
    return sort_dataframe(sessions, "scheduled_start")


def _session_options(sessions: pd.DataFrame) -> list[FilterOption]:
    return [
        FilterOption(
            value=row.id,
            label=f"{row.course_code} — {row.name}",
        )
        for row in sessions.itertuples(index=False)
    ]


def _prepare_checkins(records: list[Any]) -> pd.DataFrame:
    checkins = records_to_dataframe(records)
    if checkins.empty:
        return checkins

    missing = [column for column in CHECKIN_COLUMNS if column not in checkins.columns]
    missing.extend(column for column in ("id",) if column not in checkins.columns)
    if missing:
        raise KeyError(f"Missing TA session check-in columns: {missing}")

    checkins = convert_datetime_columns(
        checkins,
        ["checked_in_at"],
        missing="raise",
    )
    return sort_dataframe(checkins, "checked_in_at", ascending=False)


def _status_summary(checkins: pd.DataFrame) -> pd.DataFrame:
    return (
        checkins.groupby("status", as_index=False)
        .agg(checkin_count=("id", "count"))
        .sort_values("status")
        .reset_index(drop=True)
    )


def render_ta_sessions(
    current_user: dict[str, Any],
    client: APIClient | None = None,
) -> None:
    """Render the TA's development session selector and authorized records."""
    st.title("TA Session Review")
    display_name = current_user.get("full_name") or current_user.get("email") or "TA"
    st.caption(f"Review backend-authorized session check-ins for {display_name}.")

    sessions = get_ta_session_options()
    st.subheader("Relevant sessions")
    st.caption(TA_SESSION_SOURCE_MESSAGE)
    render_kpi("Development Sessions", len(sessions))
    render_table(
        sessions[SESSION_COLUMNS],
        column_config=SESSION_COLUMN_CONFIG,
        empty_message="No development sessions are available.",
    )
    selected_session = render_session_filter(
        _session_options(sessions),
        label="Session to review",
        key="ta_session_review",
    )
    if selected_session is None:
        render_empty_state("Select a session to load its authorized check-ins.")
        return

    api_client = client or APIClient()
    try:
        with loading_state("Loading session check-ins..."):
            records = authenticated_request(
                api_client,
                lambda access_token: api_client.get_session_checkins(
                    access_token,
                    selected_session,
                ),
            )
    except APIClientError as error:
        render_api_error(error)
        return

    try:
        checkins = _prepare_checkins(records)
    except (KeyError, TypeError, ValueError):
        render_api_error(APIClientError("Invalid session check-in response"))
        return

    if checkins.empty:
        render_empty_state("No check-ins were returned for this session.")
        return

    summary = _status_summary(checkins)
    count_by_status = summary.set_index("status")["checkin_count"]
    attention = checkins[checkins["status"].isin(ATTENTION_STATUSES)].copy()

    metric_columns = st.columns(3)
    metrics = (
        ("Session Check-ins", len(checkins)),
        ("Requiring Attention", len(attention)),
        ("Approved", int(count_by_status.get("approved", 0))),
    )
    for column, (label, value) in zip(metric_columns, metrics, strict=True):
        with column:
            render_kpi(label, value)

    st.subheader("Check-ins requiring attention")
    render_table(
        attention[CHECKIN_COLUMNS],
        column_config=CHECKIN_COLUMN_CONFIG,
        empty_message="No check-ins require attention for this session.",
    )

    st.subheader("Recent authorized session check-ins")
    render_table(
        checkins[CHECKIN_COLUMNS].head(10).copy(),
        column_config=CHECKIN_COLUMN_CONFIG,
        empty_message="No recent check-ins were returned for this session.",
    )

    st.subheader("Check-in details")
    selected_status = render_status_filter(
        checkins["status"].dropna().astype(str).tolist(),
        key="ta_checkin_status",
    )
    filtered_checkins = checkins
    if selected_status is not None:
        filtered_checkins = filter_equals(
            filtered_checkins,
            "status",
            selected_status,
        )
    render_table(
        filtered_checkins[CHECKIN_COLUMNS],
        column_config=CHECKIN_COLUMN_CONFIG,
        empty_message="No check-ins match the selected status.",
    )

    render_bar_chart(
        summary,
        x="status",
        y="checkin_count",
        labels={"status": "Status", "checkin_count": "Check-ins"},
        empty_message="No status data was returned for this session.",
    )
