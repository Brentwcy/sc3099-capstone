"""Live, summary-first Instructor overview."""

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from api_client import APIClient, APIClientError
from components.auth import authenticated_request
from components.charts import render_line_chart
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


SESSION_COLUMNS = [
    "scheduled_start",
    "course_code",
    "course_name",
    "name",
    "session_type",
    "status",
    "checkin_opens_at",
    "checkin_closes_at",
    "checkin_count",
    "total_enrolled",
]
SESSION_COLUMN_CONFIG = {
    "scheduled_start": "Scheduled start",
    "course_code": "Course code",
    "course_name": "Course",
    "name": "Session",
    "session_type": "Session type",
    "status": "Status",
    "checkin_opens_at": "Check-in opens",
    "checkin_closes_at": "Check-in closes",
    "checkin_count": "Check-ins",
    "total_enrolled": "Enrolled",
}
CHECKIN_COLUMNS = [
    "checked_in_at",
    "session_name",
    "student_name",
    "student_email",
    "status",
    "risk_score",
    "liveness_passed",
]
CHECKIN_COLUMN_CONFIG = {
    "checked_in_at": "Checked in",
    "session_name": "Session",
    "student_name": "Student",
    "student_email": "Email",
    "status": "Status",
    "risk_score": "Risk score",
    "liveness_passed": "Liveness passed",
}
ATTENTION_STATUSES = frozenset({"flagged", "rejected"})


def _paginated_items(payload: dict[str, Any], resource: str) -> list[Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise APIClientError(f"Invalid {resource} response")
    return payload["items"]


def _prepare_sessions(records: list[Any]) -> pd.DataFrame:
    sessions = records_to_dataframe(records)
    if sessions.empty:
        return sessions

    required = [
        "id",
        *[column for column in SESSION_COLUMNS if column != "checkin_count"],
    ]
    missing = [column for column in required if column not in sessions.columns]
    if missing:
        raise KeyError(f"Missing Instructor session columns: {missing}")

    sessions = convert_datetime_columns(
        sessions,
        [
            "scheduled_start",
            "checkin_opens_at",
            "checkin_closes_at",
        ],
        missing="raise",
    )
    return sort_dataframe(sessions, "scheduled_start")


def _prepare_checkins(records: list[Any]) -> pd.DataFrame:
    checkins = records_to_dataframe(records)
    if checkins.empty:
        return checkins

    required = ["id", "session_id", *CHECKIN_COLUMNS]
    missing = [column for column in required if column not in checkins.columns]
    if missing:
        raise KeyError(f"Missing Instructor check-in columns: {missing}")

    checkins = convert_datetime_columns(
        checkins,
        ["checked_in_at"],
        missing="raise",
    )
    return sort_dataframe(checkins, "checked_in_at", ascending=False)


def _filter_to_day(
    dataframe: pd.DataFrame,
    column: str,
    target_day: date,
) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()
    return dataframe.loc[dataframe[column].dt.date == target_day].copy()


def _checkin_kpi(
    today_sessions: pd.DataFrame,
    session_checkins: pd.DataFrame,
) -> tuple[str, int | str]:
    if not today_sessions.empty:
        enrolled = pd.to_numeric(today_sessions["total_enrolled"], errors="coerce")
        if enrolled.notna().all() and enrolled.ge(0).all():
            denominator = float(enrolled.sum())
            if denominator > 0:
                return "Check-in Rate", f"{len(session_checkins) / denominator:.0%}"

    return "Today's Check-ins", len(session_checkins)


def _checkins_for_sessions(
    checkins: pd.DataFrame,
    sessions: pd.DataFrame,
) -> pd.DataFrame:
    if checkins.empty or sessions.empty:
        return checkins.iloc[0:0].copy()
    return checkins.loc[checkins["session_id"].isin(sessions["id"])].copy()


def _add_checkin_counts(
    sessions: pd.DataFrame,
    checkins: pd.DataFrame,
) -> pd.DataFrame:
    result = sessions.copy()
    if result.empty:
        result["checkin_count"] = pd.Series(dtype="int64")
        return result

    counts = (
        checkins.groupby("session_id", as_index=False)
        .agg(checkin_count=("id", "count"))
        if not checkins.empty
        else pd.DataFrame(columns=["session_id", "checkin_count"])
    )
    count_by_session = counts.set_index("session_id")["checkin_count"]
    result["checkin_count"] = (
        result["id"].map(count_by_session).fillna(0).astype(int)
    )
    return result


def _daily_trend(checkins: pd.DataFrame) -> pd.DataFrame:
    if checkins.empty:
        return pd.DataFrame(columns=["checkin_day", "checkin_count"])

    dated = checkins.dropna(subset=["checked_in_at"]).copy()
    dated["checkin_day"] = dated["checked_in_at"].dt.floor("D")
    return (
        dated.groupby("checkin_day", as_index=False)
        .agg(checkin_count=("id", "count"))
        .sort_values("checkin_day")
        .reset_index(drop=True)
    )


def _session_options(checkins: pd.DataFrame) -> list[FilterOption]:
    sessions = checkins[["session_id", "session_name"]].drop_duplicates()
    return [
        FilterOption(value=row.session_id, label=row.session_name)
        for row in sessions.itertuples(index=False)
    ]


def render_instructor_overview(
    current_user: dict[str, Any],
    client: APIClient | None = None,
    *,
    today: date | None = None,
) -> None:
    """Render the backend-authorized Instructor dashboard overview."""
    st.title("Instructor Overview")
    display_name = (
        current_user.get("full_name")
        or current_user.get("email")
        or "Instructor"
    )
    st.caption(
        f"Today's sessions and actionable check-in information for {display_name}. "
        "Dates use UTC."
    )

    api_client = client or APIClient()
    try:
        with loading_state("Loading Instructor overview..."):
            session_payload = authenticated_request(
                api_client,
                lambda access_token: api_client.get_sessions(
                    access_token,
                    limit=100,
                ),
            )
            checkin_payload = authenticated_request(
                api_client,
                lambda access_token: api_client.get_checkins(
                    access_token,
                    limit=100,
                ),
            )
            session_records = _paginated_items(session_payload, "session")
            checkin_records = _paginated_items(checkin_payload, "check-in")
    except APIClientError as error:
        render_api_error(error)
        return

    try:
        sessions = _prepare_sessions(session_records)
        checkins = _prepare_checkins(checkin_records)
    except (KeyError, TypeError, ValueError):
        render_api_error(APIClientError("Invalid Instructor overview response"))
        return

    target_day = today or datetime.now(timezone.utc).date()
    today_sessions = _filter_to_day(sessions, "scheduled_start", target_day)
    today_session_checkins = _checkins_for_sessions(checkins, today_sessions)
    today_session_details = _add_checkin_counts(
        today_sessions,
        today_session_checkins,
    )
    attention = (
        checkins[checkins["status"].isin(ATTENTION_STATUSES)].copy()
        if not checkins.empty
        else checkins.copy()
    )
    middle_label, middle_value = _checkin_kpi(
        today_sessions,
        today_session_checkins,
    )

    metric_columns = st.columns(3)
    metrics = (
        ("Today's Sessions", len(today_sessions)),
        (middle_label, middle_value),
        ("Flagged Items Requiring Action", len(attention)),
    )
    for column, (label, value) in zip(metric_columns, metrics, strict=True):
        with column:
            render_kpi(label, value)

    st.subheader("Today's sessions")
    if today_sessions.empty:
        render_empty_state("No sessions are scheduled for today.")
    else:
        render_table(
            today_session_details[SESSION_COLUMNS],
            column_config=SESSION_COLUMN_CONFIG,
        )

    st.subheader("Flagged items requiring action")
    if attention.empty:
        render_empty_state("No flagged or rejected check-ins require attention.")
    else:
        render_table(
            attention[CHECKIN_COLUMNS],
            column_config=CHECKIN_COLUMN_CONFIG,
        )

    st.subheader("Check-ins over time")
    render_line_chart(
        _daily_trend(checkins),
        x="checkin_day",
        y="checkin_count",
        labels={"checkin_day": "Date", "checkin_count": "Check-ins"},
        empty_message="No check-in trend data is available.",
    )

    with st.expander("Detailed check-in records"):
        if checkins.empty:
            render_empty_state("No check-in records are available.")
            return

        filter_columns = st.columns(2)
        with filter_columns[0]:
            selected_session = render_session_filter(
                _session_options(checkins),
                key="instructor_checkin_session",
            )
        with filter_columns[1]:
            selected_status = render_status_filter(
                checkins["status"].dropna().astype(str).tolist(),
                key="instructor_checkin_status",
            )

        filtered_checkins = checkins
        if selected_session is not None:
            filtered_checkins = filter_equals(
                filtered_checkins,
                "session_id",
                selected_session,
            )
        if selected_status is not None:
            filtered_checkins = filter_equals(
                filtered_checkins,
                "status",
                selected_status,
            )

        render_table(
            filtered_checkins[CHECKIN_COLUMNS],
            column_config=CHECKIN_COLUMN_CONFIG,
            empty_message="No check-ins match the selected filters.",
        )
