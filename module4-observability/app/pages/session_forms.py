"""Instructor-only forms for creating and editing sessions."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import streamlit as st

from api_client import APIClient, APIClientError
from components.auth import authenticated_request
from components.feedback import render_api_error, render_empty_state
from components.filters import FilterOption, render_course_filter
from components.loading import loading_state


SESSION_TYPES = ("lecture", "tutorial", "lab", "exam")


@dataclass(frozen=True)
class SessionFormValues:
    """Normalized values collected by the create and edit forms."""

    course_id: str | None
    name: str
    session_type: str
    description: str
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: datetime | None
    checkin_closes_at: datetime | None
    venue_latitude: float | None
    venue_longitude: float | None
    venue_name: str
    geofence_radius_meters: float | None
    require_liveness_check: bool
    require_face_match: bool
    risk_threshold: float | None


def _utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("Expected a datetime value")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _datetime_input(label: str, *, key: str, value: datetime) -> datetime:
    initial = _utc_datetime(value)
    columns = st.columns(2)
    with columns[0]:
        selected_date = st.date_input(
            f"{label} date",
            value=initial.date(),
            key=f"{key}_date",
        )
    with columns[1]:
        selected_time = st.time_input(
            f"{label} time (UTC)",
            value=initial.time().replace(tzinfo=None),
            key=f"{key}_time",
        )
    if not isinstance(selected_date, date) or not isinstance(selected_time, time):
        raise TypeError("Session date and time inputs are required")
    return datetime.combine(selected_date, selected_time, tzinfo=timezone.utc)


def _optional_number(
    label: str,
    *,
    key: str,
    value: float | None,
    minimum: float,
    maximum: float,
) -> float | None:
    enabled = st.checkbox(
        f"Set {label.lower()}",
        value=value is not None,
        key=f"{key}_enabled",
    )
    if not enabled:
        return None
    default = minimum if value is None else float(value)
    return float(
        st.number_input(
            label,
            min_value=minimum,
            max_value=maximum,
            value=default,
            key=key,
        )
    )


def _initial_datetime(
    detail: Mapping[str, Any] | None,
    field: str,
    fallback: datetime,
) -> datetime:
    if detail is None:
        return fallback
    return _utc_datetime(detail[field])


def _render_session_inputs(
    *,
    key_prefix: str,
    course_options: list[FilterOption] | None = None,
    detail: Mapping[str, Any] | None = None,
) -> SessionFormValues:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    default_start = now + timedelta(days=1)
    default_end = default_start + timedelta(hours=1)

    course_id = None
    if course_options is not None:
        course_id = render_course_filter(
            course_options,
            label="Course",
            key=f"{key_prefix}_course",
            all_label="Select a course",
        )

    name = st.text_input(
        "Session name",
        value="" if detail is None else str(detail["name"]),
        key=f"{key_prefix}_name",
    )
    initial_type = "lecture" if detail is None else str(detail["session_type"])
    session_type = st.selectbox(
        "Session type",
        options=SESSION_TYPES,
        index=SESSION_TYPES.index(initial_type),
        key=f"{key_prefix}_type",
    )
    description = st.text_area(
        "Description (optional)",
        value=(
            ""
            if detail is None or detail.get("description") is None
            else str(detail["description"])
        ),
        key=f"{key_prefix}_description",
    )
    scheduled_start = _datetime_input(
        "Scheduled start",
        key=f"{key_prefix}_scheduled_start",
        value=_initial_datetime(detail, "scheduled_start", default_start),
    )
    scheduled_end = _datetime_input(
        "Scheduled end",
        key=f"{key_prefix}_scheduled_end",
        value=_initial_datetime(detail, "scheduled_end", default_end),
    )

    custom_window = st.checkbox(
        "Set check-in window",
        value=detail is not None,
        key=f"{key_prefix}_custom_checkin",
    )
    checkin_opens_at: datetime | None = None
    checkin_closes_at: datetime | None = None
    if custom_window:
        checkin_opens_at = _datetime_input(
            "Check-in opens",
            key=f"{key_prefix}_checkin_opens",
            value=_initial_datetime(
                detail,
                "checkin_opens_at",
                scheduled_start - timedelta(minutes=15),
            ),
        )
        checkin_closes_at = _datetime_input(
            "Check-in closes",
            key=f"{key_prefix}_checkin_closes",
            value=_initial_datetime(
                detail,
                "checkin_closes_at",
                scheduled_start + timedelta(minutes=30),
            ),
        )

    existing_latitude = None if detail is None else detail.get("venue_latitude")
    existing_longitude = None if detail is None else detail.get("venue_longitude")
    custom_coordinates = st.checkbox(
        "Set venue coordinates",
        value=existing_latitude is not None and existing_longitude is not None,
        key=f"{key_prefix}_custom_coordinates",
    )
    venue_latitude: float | None = None
    venue_longitude: float | None = None
    if custom_coordinates:
        coordinate_columns = st.columns(2)
        with coordinate_columns[0]:
            venue_latitude = float(
                st.number_input(
                    "Venue latitude",
                    min_value=-90.0,
                    max_value=90.0,
                    value=0.0 if existing_latitude is None else float(existing_latitude),
                    key=f"{key_prefix}_latitude",
                )
            )
        with coordinate_columns[1]:
            venue_longitude = float(
                st.number_input(
                    "Venue longitude",
                    min_value=-180.0,
                    max_value=180.0,
                    value=0.0 if existing_longitude is None else float(existing_longitude),
                    key=f"{key_prefix}_longitude",
                )
            )

    venue_name = st.text_input(
        "Venue name (optional)",
        value=(
            ""
            if detail is None or detail.get("venue_name") is None
            else str(detail["venue_name"])
        ),
        key=f"{key_prefix}_venue_name",
    )
    geofence_radius = _optional_number(
        "Geofence radius (m)",
        key=f"{key_prefix}_geofence",
        value=None if detail is None else detail.get("geofence_radius_meters"),
        minimum=0.1,
        maximum=10_000.0,
    )
    require_liveness = st.checkbox(
        "Require liveness check",
        value=True if detail is None else bool(detail["require_liveness_check"]),
        key=f"{key_prefix}_liveness",
    )
    require_face_match = st.checkbox(
        "Require face match",
        value=False if detail is None else bool(detail["require_face_match"]),
        key=f"{key_prefix}_face_match",
    )
    risk_threshold = _optional_number(
        "Risk threshold",
        key=f"{key_prefix}_risk_threshold",
        value=None if detail is None else detail.get("risk_threshold"),
        minimum=0.0,
        maximum=1.0,
    )

    return SessionFormValues(
        course_id=course_id,
        name=name,
        session_type=str(session_type),
        description=description,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        checkin_opens_at=checkin_opens_at,
        checkin_closes_at=checkin_closes_at,
        venue_latitude=venue_latitude,
        venue_longitude=venue_longitude,
        venue_name=venue_name,
        geofence_radius_meters=geofence_radius,
        require_liveness_check=require_liveness,
        require_face_match=require_face_match,
        risk_threshold=risk_threshold,
    )


def validate_session_form(
    values: SessionFormValues,
    *,
    require_course: bool,
) -> str | None:
    """Return a lightweight validation error, leaving final authority to M2."""
    if require_course and not values.course_id:
        return "Select a course."
    if not values.name.strip():
        return "Enter a session name."
    if values.scheduled_end <= values.scheduled_start:
        return "Session end must be after session start."
    if (
        values.checkin_opens_at is not None
        and values.checkin_closes_at is not None
        and values.checkin_closes_at <= values.checkin_opens_at
    ):
        return "Check-in close must be after check-in open."
    if (values.venue_latitude is None) != (values.venue_longitude is None):
        return "Venue latitude and longitude must be provided together."
    return None


def _optional_create_fields(values: SessionFormValues) -> dict[str, Any]:
    candidates = {
        "description": values.description.strip() or None,
        "checkin_opens_at": values.checkin_opens_at,
        "checkin_closes_at": values.checkin_closes_at,
        "venue_latitude": values.venue_latitude,
        "venue_longitude": values.venue_longitude,
        "venue_name": values.venue_name.strip() or None,
        "geofence_radius_meters": values.geofence_radius_meters,
        "risk_threshold": values.risk_threshold,
    }
    return {
        field: value.isoformat() if isinstance(value, datetime) else value
        for field, value in candidates.items()
        if value is not None
    }


def build_create_payload(values: SessionFormValues) -> dict[str, Any]:
    """Build a SessionCreate payload without null or lifecycle fields."""
    return {
        "course_id": values.course_id,
        "name": values.name.strip(),
        "session_type": values.session_type,
        "scheduled_start": values.scheduled_start.isoformat(),
        "scheduled_end": values.scheduled_end.isoformat(),
        "require_liveness_check": values.require_liveness_check,
        "require_face_match": values.require_face_match,
        **_optional_create_fields(values),
    }


def _changed_datetime(
    payload: dict[str, Any],
    detail: Mapping[str, Any],
    field: str,
    value: datetime | None,
) -> None:
    if value is not None and _utc_datetime(detail[field]) != _utc_datetime(value):
        payload[field] = value.isoformat()


def build_update_payload(
    detail: Mapping[str, Any],
    values: SessionFormValues,
) -> dict[str, Any]:
    """Build a SessionUpdate payload containing only changed editable fields."""
    payload: dict[str, Any] = {}
    text_values = {
        "name": values.name.strip(),
        "session_type": values.session_type,
        "description": values.description.strip(),
        "venue_name": values.venue_name.strip(),
    }
    for field, value in text_values.items():
        current = detail.get(field)
        current_text = "" if current is None else str(current)
        if value != current_text:
            payload[field] = value

    _changed_datetime(payload, detail, "scheduled_start", values.scheduled_start)
    _changed_datetime(payload, detail, "scheduled_end", values.scheduled_end)
    _changed_datetime(payload, detail, "checkin_opens_at", values.checkin_opens_at)
    _changed_datetime(payload, detail, "checkin_closes_at", values.checkin_closes_at)

    optional_numbers = {
        "venue_latitude": values.venue_latitude,
        "venue_longitude": values.venue_longitude,
        "geofence_radius_meters": values.geofence_radius_meters,
        "risk_threshold": values.risk_threshold,
    }
    for field, value in optional_numbers.items():
        if value != detail.get(field):
            payload[field] = value

    boolean_values = {
        "require_liveness_check": values.require_liveness_check,
        "require_face_match": values.require_face_match,
    }
    for field, value in boolean_values.items():
        if value != detail.get(field):
            payload[field] = value
    return payload


def _course_options(payload: dict[str, Any]) -> list[FilterOption]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise APIClientError("Invalid course listing response")
    options: list[FilterOption] = []
    for course in payload["items"]:
        if not isinstance(course, Mapping):
            raise APIClientError("Invalid course listing response")
        course_id = course.get("id")
        code = course.get("code")
        name = course.get("name")
        if not all(isinstance(value, str) and value for value in (course_id, code, name)):
            raise APIClientError("Invalid course listing response")
        options.append(FilterOption(value=course_id, label=f"{code} — {name}"))
    return options


def render_create_session_form(client: APIClient) -> bool:
    """Render and submit the Instructor-only SessionCreate form."""
    if st.session_state.role != "instructor":
        return False

    st.subheader("Create session")
    try:
        with loading_state("Loading active courses..."):
            course_payload = authenticated_request(
                client,
                lambda access_token: client.get_courses(
                    access_token,
                    is_active=True,
                    limit=100,
                ),
            )
        course_options = _course_options(course_payload)
    except APIClientError as error:
        render_api_error(error)
        return False

    if not course_options:
        render_empty_state("No active courses are available for session creation.")
        return False

    with st.form("create-session-form"):
        values = _render_session_inputs(
            key_prefix="create_session",
            course_options=course_options,
        )
        submitted = st.form_submit_button("Create session")
    if not submitted:
        return False

    validation_error = validate_session_form(values, require_course=True)
    if validation_error is not None:
        st.error(validation_error)
        return False
    payload = build_create_payload(values)
    try:
        with loading_state("Creating session..."):
            authenticated_request(
                client,
                lambda access_token: client.create_session(access_token, payload),
            )
    except APIClientError as error:
        render_api_error(error)
        return False

    st.success("Session created successfully.")
    st.rerun()
    return True


def render_edit_session_form(
    client: APIClient,
    detail: Mapping[str, Any],
) -> bool:
    """Render and submit an Instructor-only partial SessionUpdate form."""
    if st.session_state.role != "instructor":
        return False

    session_id = detail.get("id")
    if not isinstance(session_id, str) or not session_id:
        render_api_error(APIClientError("Invalid session detail response"))
        return False

    st.subheader("Edit selected session")
    with st.form(f"edit-session-form-{session_id}"):
        values = _render_session_inputs(
            key_prefix=f"edit_session_{session_id}",
            detail=detail,
        )
        submitted = st.form_submit_button("Save changes")
    if not submitted:
        return False

    validation_error = validate_session_form(values, require_course=False)
    if validation_error is not None:
        st.error(validation_error)
        return False
    payload = build_update_payload(detail, values)
    if not payload:
        st.info("No session fields were changed.")
        return False

    try:
        with loading_state("Updating session..."):
            authenticated_request(
                client,
                lambda access_token: client.update_session(
                    access_token,
                    session_id,
                    payload,
                ),
            )
    except APIClientError as error:
        render_api_error(error)
        return False

    st.success("Session updated successfully.")
    st.rerun()
    return True
