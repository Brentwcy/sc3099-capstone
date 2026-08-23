"""Week 1 Streamlit shell for the SAIV observability dashboard."""

import streamlit as st

from components.navigation import render_sidebar
from pages import render_page
from utils.mock_data import MOCK_USERS, PAGE_NAMES


st.set_page_config(
    page_title="SAIV Dashboard",
    page_icon="📊",
    layout="wide",
)


def main() -> None:
    """Render the mock-role dashboard and its Week 1 page shells."""
    selected_page, current_user = render_sidebar(PAGE_NAMES, MOCK_USERS)
    render_page(selected_page, current_user)


if __name__ == "__main__":
    main()
