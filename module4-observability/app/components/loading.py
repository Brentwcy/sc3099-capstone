"""Consistent loading-state behavior for synchronous dashboard work."""

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


@contextmanager
def loading_state(message: str = "Loading...") -> Iterator[None]:
    """Show a spinner while work runs and allow all failures to propagate."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("loading message must be a non-empty string")

    with st.spinner(message):
        yield
