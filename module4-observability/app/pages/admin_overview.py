"""Live, system-wide Admin overview."""

from typing import Any

import pandas as pd
import streamlit as st

from api_client import APIClient, APIClientError
from components.auth import authenticated_request
from components.charts import render_bar_chart
from components.feedback import render_api_error, render_empty_state
from components.filters import render_status_filter
from components.kpi import render_kpi
from components.loading import loading_state
from components.tables import render_table
from utils.dataframes import (
    convert_datetime_columns,
    fill_missing_values,
    filter_equals,
    records_to_dataframe,
    sort_dataframe,
)


COURSE_COLUMNS = ["code", "name", "semester", "is_active", "venue_name"]
COURSE_COLUMN_CONFIG = {
    "code": "Course code",
    "name": "Course",
    "semester": "Semester",
    "is_active": "Active",
    "venue_name": "Venue",
}
AUDIT_COLUMNS = ["timestamp", "user_email", "action", "resource_type", "success"]
AUDIT_COLUMN_CONFIG = {
    "timestamp": "Timestamp",
    "user_email": "User",
    "action": "Action",
    "resource_type": "Resource type",
    "success": "Success",
}
CHECKIN_COLUMNS = [
    "checked_in_at",
    "session_name",
    "student_name",
    "student_email",
    "status",
]
CHECKIN_COLUMN_CONFIG = {
    "checked_in_at": "Checked in",
    "session_name": "Session",
    "student_name": "Student",
    "student_email": "Email",
    "status": "Status",
}


def _paginated_data(
    payload: dict[str, Any],
    resource: str,
) -> tuple[list[Any], int]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise APIClientError(f"Invalid {resource} response")

    total = payload.get("total")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise APIClientError(f"Invalid {resource} response")
    return payload["items"], total


def _prepare_courses(records: list[Any]) -> pd.DataFrame:
    courses = records_to_dataframe(records)
    if courses.empty:
        return courses

    missing = [column for column in COURSE_COLUMNS if column not in courses.columns]
    if missing:
        raise KeyError(f"Missing Admin course columns: {missing}")

    courses = fill_missing_values(courses, {"venue_name": "Not specified"})
    return sort_dataframe(courses, "code")


def _prepare_checkins(records: list[Any]) -> pd.DataFrame:
    checkins = records_to_dataframe(records)
    if checkins.empty:
        return checkins

    required = ["id", *CHECKIN_COLUMNS]
    missing = [column for column in required if column not in checkins.columns]
    if missing:
        raise KeyError(f"Missing Admin check-in columns: {missing}")

    checkins = convert_datetime_columns(
        checkins,
        ["checked_in_at"],
        missing="raise",
    )
    return sort_dataframe(checkins, "checked_in_at", ascending=False)


def _prepare_audit_logs(records: list[Any]) -> pd.DataFrame:
    audit_logs = records_to_dataframe(records)
    if audit_logs.empty:
        return audit_logs

    required = ["id", *AUDIT_COLUMNS]
    missing = [column for column in required if column not in audit_logs.columns]
    if missing:
        raise KeyError(f"Missing Admin audit columns: {missing}")

    audit_logs = convert_datetime_columns(
        audit_logs,
        ["timestamp"],
        missing="raise",
    )
    audit_logs = fill_missing_values(
        audit_logs,
        {
            "user_email": "System",
            "resource_type": "Not specified",
        },
    )
    return sort_dataframe(audit_logs, "timestamp", ascending=False)


def _status_summary(checkins: pd.DataFrame) -> pd.DataFrame:
    if checkins.empty:
        return pd.DataFrame(columns=["status", "checkin_count"])

    summary = (
        checkins["status"]
        .value_counts()
        .rename_axis("status")
        .reset_index(name="checkin_count")
    )
    return sort_dataframe(summary, "status")


def _health_label(result: dict[str, Any]) -> str:
    if result.get("healthy") is True:
        return "Healthy"
    if result.get("reachable") is True:
        return "Degraded"
    return "Unavailable"


def render_admin_overview(
    current_user: dict[str, Any],
    client: APIClient | None = None,
) -> None:
    """Render the backend-authorized Admin dashboard overview."""
    st.title("Admin Overview")
    display_name = (
        current_user.get("full_name")
        or current_user.get("email")
        or "Administrator"
    )
    st.caption(
        f"System-wide business activity for {display_name}. "
        "Technical monitoring remains separate."
    )

    api_client = client or APIClient()
    try:
        with loading_state("Loading Admin overview..."):
            active_course_payload = authenticated_request(
                api_client,
                lambda access_token: api_client.get_courses(
                    access_token,
                    is_active=True,
                    limit=100,
                ),
            )
            inactive_course_payload = authenticated_request(
                api_client,
                lambda access_token: api_client.get_courses(
                    access_token,
                    is_active=False,
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
            audit_payload = authenticated_request(
                api_client,
                lambda access_token: api_client.get_audit_logs(
                    access_token,
                    limit=20,
                ),
            )
            health = api_client.check_health()

            active_records, active_total = _paginated_data(
                active_course_payload,
                "active course",
            )
            inactive_records, inactive_total = _paginated_data(
                inactive_course_payload,
                "inactive course",
            )
            checkin_records, _checkin_total = _paginated_data(
                checkin_payload,
                "check-in",
            )
            audit_records, _audit_total = _paginated_data(
                audit_payload,
                "audit",
            )
    except APIClientError as error:
        render_api_error(error)
        return

    try:
        courses = _prepare_courses([*active_records, *inactive_records])
        checkins = _prepare_checkins(checkin_records)
        audit_logs = _prepare_audit_logs(audit_records)
        active_courses = (
            filter_equals(courses, "is_active", True)
            if not courses.empty
            else courses.copy()
        )
    except (KeyError, TypeError, ValueError):
        render_api_error(APIClientError("Invalid Admin overview response"))
        return

    metric_columns = st.columns(4)
    metrics = (
        ("Total Courses", active_total + inactive_total),
        ("Active Courses", active_total),
        ("Recent Check-ins", len(checkins)),
        ("Recent Audit Events", len(audit_logs)),
    )
    for column, (label, value) in zip(metric_columns, metrics, strict=True):
        with column:
            render_kpi(label, value)

    st.subheader("Course overview")
    if courses.empty:
        render_empty_state("No courses were returned for this account.")
    else:
        render_table(
            courses[COURSE_COLUMNS],
            column_config=COURSE_COLUMN_CONFIG,
        )
        st.caption(f"{len(active_courses)} active courses are shown in this result set.")

    st.subheader("Recent check-in activity")
    if checkins.empty:
        render_empty_state("No recent check-in activity was returned.")
    else:
        render_bar_chart(
            _status_summary(checkins),
            x="status",
            y="checkin_count",
            labels={"status": "Status", "checkin_count": "Check-ins"},
        )

    st.subheader("Recent audit activity")
    if audit_logs.empty:
        render_empty_state("No recent audit events were returned.")
    else:
        render_table(
            audit_logs[AUDIT_COLUMNS],
            column_config=AUDIT_COLUMN_CONFIG,
        )

    with st.expander("Recent check-in records"):
        if checkins.empty:
            render_empty_state("No recent check-in records are available.")
        else:
            selected_status = render_status_filter(
                checkins["status"].dropna().astype(str).tolist(),
                key="admin_checkin_status",
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

    st.subheader("Admin destinations")
    st.markdown(
        "Use **Audit Logs** in the sidebar for detailed audit browsing, and "
        "**System Metrics** for technical monitoring."
    )
    st.caption(f"Current Module 2 API status: {_health_label(health)}.")
