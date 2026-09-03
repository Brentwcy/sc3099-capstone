"""Permission-aware page routing for the dashboard shell."""

from typing import Any

import streamlit as st

from pages.admin_overview import render_admin_overview
from pages.instructor_overview import render_instructor_overview
from pages.shells import render_shell
from pages.student_attendance import render_student_attendance
from pages.ta_sessions import render_ta_sessions
from utils.permissions import resolve_page


def render_page(page_name: str, current_user: dict[str, Any]) -> None:
    """Render an allowed page or fall back safely for the current role."""
    resolved_page = resolve_page(st.session_state.role, page_name)
    if resolved_page is None:
        st.error("No dashboard pages are available for this account.")
        return

    if resolved_page == "My Attendance":
        render_student_attendance(current_user)
    elif resolved_page == "Sessions" and st.session_state.role == "ta":
        render_ta_sessions(current_user)
    elif resolved_page == "Overview" and st.session_state.role == "instructor":
        render_instructor_overview(current_user)
    elif resolved_page == "Overview" and st.session_state.role == "admin":
        render_admin_overview(current_user)
    else:
        render_shell(resolved_page, st.session_state.role)
