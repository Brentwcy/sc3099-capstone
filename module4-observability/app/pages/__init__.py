"""Permission-aware page routing for the dashboard shell."""

from typing import Any

import streamlit as st

from pages.overview import render_overview
from pages.shells import render_shell
from utils.permissions import resolve_page


def render_page(page_name: str, current_user: dict[str, Any]) -> None:
    """Render an allowed page or fall back safely for the current role."""
    resolved_page = resolve_page(st.session_state.role, page_name)
    if resolved_page is None:
        st.error("No dashboard pages are available for this account.")
        return

    if resolved_page == "Overview":
        render_overview(current_user)
    else:
        render_shell(resolved_page, st.session_state.role)
