"""Week 1 Streamlit shell for the SAIV observability dashboard."""

import streamlit as st

from api_client import APIClient
from components.auth import initialize_auth_state, render_login, validate_authenticated_session
from components.navigation import render_sidebar
from pages import render_page


st.set_page_config(
    page_title="SAIV Dashboard",
    page_icon="📊",
    layout="wide",
)


def main() -> None:
    """Render the login gate or the authenticated Week 1 dashboard."""
    initialize_auth_state()
    client = APIClient()
    if not st.session_state.authenticated:
        render_login(client)
        return

    validation_error = validate_authenticated_session(client)
    if validation_error is not None:
        st.error(validation_error)
        if not st.session_state.authenticated:
            render_login(client)
        return

    selected_page = render_sidebar()
    if selected_page is None:
        return
    render_page(selected_page, st.session_state.current_user)


if __name__ == "__main__":
    main()
