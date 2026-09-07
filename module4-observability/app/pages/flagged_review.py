"""Actionable flagged and appealed check-in review workflow."""

from typing import Any

import pandas as pd
import streamlit as st

from api_client import APIClient, APIClientError
from components.auth import authenticated_request
from components.feedback import render_api_error, render_empty_state
from components.kpi import render_kpi
from components.loading import loading_state
from components.tables import render_table
from utils.dataframes import convert_datetime_columns, records_to_dataframe, sort_dataframe


QUEUE_COLUMNS = [
    "checked_in_at",
    "course_code",
    "session_name",
    "student_name",
    "student_email",
    "status",
    "risk_score",
]
QUEUE_COLUMN_CONFIG = {
    "checked_in_at": "Checked in",
    "course_code": "Course",
    "session_name": "Session",
    "student_name": "Student",
    "student_email": "Email",
    "status": "Status",
    "risk_score": "Risk score",
}


def _queue_items(payload: dict[str, Any]) -> list[Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise APIClientError("Invalid flagged review response")
    return payload["items"]


def _prepare_queue(records: list[Any]) -> pd.DataFrame:
    queue = records_to_dataframe(records)
    if queue.empty:
        return queue
    required = ["id", "risk_factors", *QUEUE_COLUMNS]
    missing = [column for column in required if column not in queue.columns]
    if missing:
        raise KeyError(f"Missing flagged review columns: {missing}")
    queue = convert_datetime_columns(queue, ["checked_in_at"], missing="raise")
    return sort_dataframe(queue, "checked_in_at", ascending=False)


def _item_label(item: dict[str, Any]) -> str:
    return (
        f"{item['course_code']} — {item['session_name']} — "
        f"{item['student_name']} ({item['status']})"
    )


def render_flagged_review(
    current_user: dict[str, Any],
    client: APIClient | None = None,
) -> None:
    """Render the role-gated review queue and one-decision form."""
    st.title("Flagged Review")
    display_name = current_user.get("full_name") or current_user.get("email") or "Reviewer"
    st.caption(f"Review flagged and appealed check-ins as {display_name}.")

    completed_message = st.session_state.pop("flagged_review_completed", None)
    if completed_message:
        st.success(completed_message)

    api_client = client or APIClient()
    try:
        with loading_state("Loading flagged check-ins..."):
            payload = authenticated_request(
                api_client,
                lambda access_token: api_client.get_flagged_checkins(
                    access_token,
                    limit=100,
                ),
            )
            records = _queue_items(payload)
    except APIClientError as error:
        render_api_error(error)
        return

    try:
        queue = _prepare_queue(records)
    except (KeyError, TypeError, ValueError):
        render_api_error(APIClientError("Invalid flagged review response"))
        return

    render_kpi("Awaiting Review", len(queue))
    if queue.empty:
        render_empty_state("No flagged or appealed check-ins require review.")
        return

    render_table(queue[QUEUE_COLUMNS], column_config=QUEUE_COLUMN_CONFIG)
    items_by_id = {str(item["id"]): item for item in records}
    selected_id = st.selectbox(
        "Check-in to review",
        options=list(items_by_id),
        format_func=lambda item_id: _item_label(items_by_id[item_id]),
    )
    selected = items_by_id[selected_id]

    st.subheader("Review context")
    st.write(
        {
            "course": f"{selected['course_code']} — {selected.get('course_name', '')}",
            "session": selected["session_name"],
            "student": selected["student_name"],
            "status": selected["status"],
            "risk_score": selected["risk_score"],
            "risk_factors": selected["risk_factors"],
            "appeal_reason": selected.get("appeal_reason"),
        }
    )

    with st.form(f"review-checkin-{selected_id}"):
        decision_label = st.radio(
            "Decision",
            options=("Approve", "Reject"),
            horizontal=True,
        )
        review_notes = st.text_area(
            "Review notes",
            max_chars=2000,
            help="Record the evidence used for the decision.",
        )
        submitted = st.form_submit_button("Submit final decision")

    if not submitted:
        return
    if not review_notes.strip():
        st.warning("Review notes are required.")
        return

    decision = "approved" if decision_label == "Approve" else "rejected"
    try:
        with loading_state("Submitting review decision..."):
            authenticated_request(
                api_client,
                lambda access_token: api_client.review_checkin(
                    access_token,
                    selected_id,
                    status=decision,
                    review_notes=review_notes.strip(),
                ),
            )
    except APIClientError as error:
        render_api_error(error)
        return

    st.session_state["flagged_review_completed"] = (
        f"Check-in {selected_id} was {decision}."
    )
    st.rerun()
