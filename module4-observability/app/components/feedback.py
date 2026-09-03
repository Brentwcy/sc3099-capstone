"""Safe, reusable feedback rendering for dashboard pages."""

import streamlit as st

from api_client import (
    APIClientError,
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
)


def render_api_error(error: APIClientError) -> None:
    """Render a safe user-facing message for an API client failure."""
    if isinstance(error, APIResponseError):
        if error.status_code == 403:
            st.error("You do not have permission to perform this action.")
            return
        if error.status_code == 429:
            st.warning("Too many requests. Please try again later.")
            return
        st.error("The server could not complete the request. Please try again later.")
        return

    if isinstance(error, APITimeoutError):
        st.error("The request timed out. Please try again.")
        return

    if isinstance(error, APIConnectionError):
        st.error("The backend is currently unavailable. Please try again later.")
        return

    st.error("Something went wrong while contacting the backend. Please try again later.")


def render_empty_state(message: str) -> None:
    """Render feedback for a successful request that returned no data."""
    st.info(message)
