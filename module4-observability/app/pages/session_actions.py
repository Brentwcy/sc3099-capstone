"""Instructor-only lifecycle and deletion controls for sessions."""

from collections.abc import Mapping
from typing import Any

import streamlit as st

from api_client import APIClient, APIClientError
from components.auth import authenticated_request
from components.feedback import render_api_error
from components.loading import loading_state


SESSION_SELECTION_KEY = "instructor_session_detail"
LIFECYCLE_ACTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "scheduled": (
        ("Activate Session", "active"),
        ("Cancel Session", "cancelled"),
    ),
    "active": (
        ("Close Session", "closed"),
        ("Cancel Session", "cancelled"),
    ),
    "closed": (("Cancel Session", "cancelled"),),
    "cancelled": (),
}
LIFECYCLE_SUCCESS_MESSAGES = {
    "active": "Session activated successfully.",
    "closed": "Session closed successfully.",
    "cancelled": "Session cancelled successfully.",
}


def _apply_lifecycle_status(
    client: APIClient,
    session_id: str,
    target_status: str,
) -> bool:
    """Apply one confirmed lifecycle transition using a status-only PATCH."""
    try:
        with loading_state(f"Updating session to {target_status}..."):
            authenticated_request(
                client,
                lambda access_token: client.update_session(
                    access_token,
                    session_id,
                    {"status": target_status},
                ),
            )
    except APIClientError as error:
        render_api_error(error)
        return False

    st.success(LIFECYCLE_SUCCESS_MESSAGES[target_status])
    st.rerun()
    return True


def _render_scheduled_delete(client: APIClient, session_id: str) -> bool:
    """Require confirmation and delete an authoritative scheduled session."""
    confirmation_key = f"delete_session_confirmed_{session_id}"
    st.warning("Deleting this scheduled session cannot be undone.")
    confirmed = st.checkbox(
        "I understand and want to delete this session.",
        value=False,
        key=confirmation_key,
    )
    delete_clicked = st.button(
        "Delete Session",
        key=f"delete_session_{session_id}",
        disabled=not confirmed,
    )
    if not confirmed or not delete_clicked:
        return False

    try:
        with loading_state("Deleting session..."):
            authenticated_request(
                client,
                lambda access_token: client.delete_session(
                    access_token,
                    session_id,
                ),
            )
    except APIClientError as error:
        render_api_error(error)
        return False

    st.session_state.pop(SESSION_SELECTION_KEY, None)
    st.session_state.pop(confirmation_key, None)
    st.success("Session deleted successfully.")
    st.rerun()
    return True


def render_session_actions(
    client: APIClient,
    detail: Mapping[str, Any],
) -> bool:
    """Render actions allowed by the authoritative status for an Instructor."""
    if st.session_state.role != "instructor":
        return False

    session_id = detail.get("id")
    current_status = detail.get("status")
    if (
        not isinstance(session_id, str)
        or not session_id
        or current_status not in LIFECYCLE_ACTIONS
    ):
        return False

    actions = LIFECYCLE_ACTIONS[current_status]
    if not actions:
        return False

    st.subheader("Session actions")
    for label, target_status in actions:
        clicked = st.button(
            label,
            key=f"session_{target_status}_{session_id}",
        )
        if clicked:
            return _apply_lifecycle_status(client, session_id, target_status)

    if current_status == "scheduled":
        return _render_scheduled_delete(client, session_id)
    return False
