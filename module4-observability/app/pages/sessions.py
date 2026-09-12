"""Role-aware session discovery and authoritative session details."""

from datetime import date, datetime, time, timezone
from typing import Any

import pandas as pd
import streamlit as st

from api_client import APIClient, APIClientError
from components.auth import authenticated_request
from components.feedback import render_api_error, render_empty_state
from components.filters import (
    FilterOption,
    render_date_range_filter,
    render_session_filter,
    render_status_filter,
)
from components.loading import loading_state
from components.tables import render_table
from utils.dataframes import (
    convert_datetime_columns,
    records_to_dataframe,
    sort_dataframe,
)


SESSION_STATUSES = ("scheduled", "active", "closed", "cancelled")
SESSION_LIST_COLUMNS = [
    "scheduled_start",
    "scheduled_end",
    "course_code",
    "course_name",
    "name",
    "session_type",
    "status",
    "venue_name",
    "total_enrolled",
    "checked_in_count",
]
SESSION_LIST_COLUMN_CONFIG = {
    "scheduled_start": "Scheduled start",
    "scheduled_end": "Scheduled end",
    "course_code": "Course code",
    "course_name": "Course",
    "name": "Session",
    "session_type": "Session type",
    "status": "Status",
    "venue_name": "Venue",
    "total_enrolled": "Enrolled",
    "checked_in_count": "Checked in",
}
SESSION_DETAIL_FIELDS = (
    "course_code",
    "course_name",
    "name",
    "session_type",
    "description",
    "status",
    "scheduled_start",
    "scheduled_end",
    "checkin_opens_at",
    "checkin_closes_at",
    "actual_start",
    "actual_end",
    "venue_name",
    "geofence_radius_meters",
    "require_liveness_check",
    "require_face_match",
    "risk_threshold",
    "qr_code_enabled",
    "total_enrolled",
    "checked_in_count",
)
SESSION_DETAIL_LABELS = {
    "course_code": "Course code",
    "course_name": "Course",
    "name": "Session",
    "session_type": "Session type",
    "description": "Description",
    "status": "Status",
    "scheduled_start": "Scheduled start",
    "scheduled_end": "Scheduled end",
    "checkin_opens_at": "Check-in opens",
    "checkin_closes_at": "Check-in closes",
    "actual_start": "Actual start",
    "actual_end": "Actual end",
    "venue_name": "Venue",
    "geofence_radius_meters": "Geofence radius (m)",
    "require_liveness_check": "Liveness required",
    "require_face_match": "Face match required",
    "risk_threshold": "Risk threshold",
    "qr_code_enabled": "QR code enabled",
    "total_enrolled": "Enrolled",
    "checked_in_count": "Checked in",
}
SESSION_DATETIME_FIELDS = (
    "scheduled_start",
    "scheduled_end",
    "checkin_opens_at",
    "checkin_closes_at",
    "actual_start",
    "actual_end",
)


def _paginated_session_items(payload: dict[str, Any]) -> list[Any]:
    """Extract the confirmed paginated session result shape."""
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise APIClientError("Invalid session listing response")
    return payload["items"]


def _date_bound(value: date | None, *, end_of_day: bool = False) -> str | None:
    if value is None:
        return None
    boundary = time.max if end_of_day else time.min
    return datetime.combine(value, boundary, tzinfo=timezone.utc).isoformat()


def discover_sessions(
    client: APIClient,
    role: str,
    *,
    status: str | None = None,
    upcoming: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Any]:
    """Return sessions from the backend endpoint authorized for the role."""
    if role == "ta":
        # M2 has no per-TA course assignment model, so use its authorized result as-is.
        return authenticated_request(
            client,
            lambda access_token: client.get_my_sessions(
                access_token,
                status=status,
                upcoming=upcoming,
                limit=100,
            ),
        )

    if role in {"instructor", "admin"}:
        payload = authenticated_request(
            client,
            lambda access_token: client.get_sessions(
                access_token,
                status=status,
                start_date=_date_bound(start_date),
                end_date=_date_bound(end_date, end_of_day=True),
                limit=100,
            ),
        )
        return _paginated_session_items(payload)

    raise APIClientError("Session discovery is unavailable for this role")


def _prepare_sessions(records: list[Any]) -> pd.DataFrame:
    sessions = records_to_dataframe(records)
    if sessions.empty:
        return sessions

    required = ["id", "course_id", *SESSION_LIST_COLUMNS]
    missing = [column for column in required if column not in sessions.columns]
    if missing:
        raise KeyError(f"Missing session listing columns: {missing}")

    sessions = convert_datetime_columns(
        sessions,
        ["scheduled_start", "scheduled_end"],
        missing="raise",
    )
    return sort_dataframe(sessions, "scheduled_start", ascending=False)


def _session_options(sessions: pd.DataFrame) -> list[FilterOption]:
    options: list[FilterOption] = []
    for row in sessions.itertuples(index=False):
        course_label = row.course_code or row.course_name or row.course_id
        options.append(
            FilterOption(
                value=row.id,
                label=f"{course_label} — {row.name}",
            )
        )
    return options


def _display_value(field: str, value: Any) -> str:
    if value is None or pd.isna(value):
        return "Not specified"
    if field in {"require_liveness_check", "require_face_match", "qr_code_enabled"}:
        return "Yes" if bool(value) else "No"
    return str(value)


def _prepare_session_detail(detail: dict[str, Any]) -> pd.DataFrame:
    if not isinstance(detail, dict):
        raise TypeError("Session detail must be an object")

    required = ["id", *SESSION_DETAIL_FIELDS]
    missing = [field for field in required if field not in detail]
    if missing:
        raise KeyError(f"Missing session detail fields: {missing}")

    prepared = convert_datetime_columns(
        records_to_dataframe([detail]),
        SESSION_DATETIME_FIELDS,
        missing="raise",
    ).iloc[0]
    return pd.DataFrame(
        {
            "Field": [SESSION_DETAIL_LABELS[field] for field in SESSION_DETAIL_FIELDS],
            "Value": [
                _display_value(field, prepared[field])
                for field in SESSION_DETAIL_FIELDS
            ],
        }
    )


def render_session_discovery(role: str, client: APIClient) -> str | None:
    """Render role-safe discovery, selection, and authoritative detail."""
    st.subheader("Discover sessions")
    selected_status = render_status_filter(
        SESSION_STATUSES,
        key=f"{role}_session_status",
    )
    upcoming = False
    start_date: date | None = None
    end_date: date | None = None
    if role == "ta":
        upcoming = st.checkbox(
            "Upcoming sessions only",
            value=False,
            key="ta_sessions_upcoming",
        )
    else:
        start_date, end_date = render_date_range_filter(
            key_prefix=f"{role}_sessions",
        )

    try:
        with loading_state("Loading sessions..."):
            records = discover_sessions(
                client,
                role,
                status=selected_status,
                upcoming=upcoming,
                start_date=start_date,
                end_date=end_date,
            )
        sessions = _prepare_sessions(records)
    except APIClientError as error:
        render_api_error(error)
        return None
    except (KeyError, TypeError, ValueError):
        render_api_error(APIClientError("Invalid session listing response"))
        return None

    if sessions.empty:
        render_empty_state("No sessions match the selected filters.")
        return None

    render_table(
        sessions[SESSION_LIST_COLUMNS],
        column_config=SESSION_LIST_COLUMN_CONFIG,
    )
    selected_session = render_session_filter(
        _session_options(sessions),
        label="Session details",
        key=f"{role}_session_detail",
        all_label="Select a session",
    )
    if selected_session is None:
        render_empty_state("Select a session to view its details.")
        return None

    try:
        with loading_state("Loading session details..."):
            detail = authenticated_request(
                client,
                lambda access_token: client.get_session(
                    access_token,
                    selected_session,
                ),
            )
        detail_table = _prepare_session_detail(detail)
    except APIClientError as error:
        render_api_error(error)
        return None
    except (KeyError, TypeError, ValueError):
        render_api_error(APIClientError("Invalid session detail response"))
        return None

    st.subheader("Session detail")
    render_table(
        detail_table,
        column_config={"Field": "Field", "Value": "Value"},
    )
    return selected_session


def render_sessions(
    current_user: dict[str, Any],
    client: APIClient | None = None,
) -> None:
    """Render Instructor/Admin session discovery and detail."""
    role = st.session_state.role
    st.title("Sessions")
    display_name = (
        current_user.get("full_name")
        or current_user.get("email")
        or role.title()
    )
    st.caption(f"Browse backend-authorized sessions for {display_name}. Dates use UTC.")
    render_session_discovery(role, client or APIClient())
