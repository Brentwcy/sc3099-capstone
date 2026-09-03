"""Placeholder pages for allowed routes that are not implemented yet."""

import streamlit as st


PAGE_DESCRIPTIONS = {
    "Check-ins": "Check-in records will be added in a later week.",
    "Flagged Review": "The flagged check-in review queue will be added in a later week.",
    "Analytics": "Attendance analytics will be added in a later week.",
    "Exports": "Attendance export tools will be added in a later week.",
    "Audit Logs": "Audit log browsing will be added in a later week.",
    "System Metrics": "System metrics will be added in a later week.",
}

SESSION_DESCRIPTIONS = {
    "student": "Your relevant, read-only session information will be shown here in a later week.",
    "instructor": "Session management will be added in a later week.",
}


def render_shell(page_name: str, role: str) -> None:
    """Render a named navigation shell with no later-week behaviour."""
    st.title(page_name)
    if page_name == "Sessions":
        st.info(SESSION_DESCRIPTIONS[role])
    else:
        st.info(PAGE_DESCRIPTIONS[page_name])
