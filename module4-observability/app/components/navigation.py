"""Sidebar controls for mock roles and Week 1 navigation."""

from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st


def render_sidebar(
    page_names: Sequence[str],
    mock_users: Mapping[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """Return the selected page and mock user without enforcing RBAC."""
    st.sidebar.title("SAIV")
    selected_role = st.sidebar.selectbox(
        "Mock role",
        options=list(mock_users),
        key="mock_role",
    )
    current_user = mock_users[selected_role]
    st.session_state["mock_user"] = current_user
    st.sidebar.caption(current_user["email"])
    st.sidebar.caption("Week 1 mock state only — all roles can see all pages.")
    selected_page = st.sidebar.radio("Navigation", page_names)
    return selected_page, current_user
