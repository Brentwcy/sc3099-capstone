"""Role-aware sidebar navigation for authenticated users."""

import streamlit as st

from components.auth import clear_auth_state
from utils.permissions import get_allowed_pages, resolve_page


def render_sidebar() -> str | None:
    """Render and return navigation permitted for the authenticated role."""
    st.sidebar.title("SAIV")
    current_user = st.session_state.current_user or {}
    st.sidebar.caption(current_user.get("email", "Authenticated user"))
    st.sidebar.caption(f"Role: {st.session_state.role}")

    if st.sidebar.button("Logout", use_container_width=True):
        clear_auth_state()
        st.session_state.pop("selected_page", None)
        st.rerun()
        return None

    allowed_pages = get_allowed_pages(st.session_state.role)
    if not allowed_pages:
        st.sidebar.error("No dashboard pages are available for this account.")
        return None

    resolved_page = resolve_page(
        st.session_state.role,
        st.session_state.get("selected_page"),
    )
    if st.session_state.get("selected_page") != resolved_page:
        st.session_state["selected_page"] = resolved_page

    return st.sidebar.radio(
        "Navigation",
        options=allowed_pages,
        key="selected_page",
    )
