"""Reusable KPI rendering for dashboard pages."""

from typing import Any

import streamlit as st


def render_kpi(
    label: str,
    value: Any,
    *,
    delta: Any | None = None,
    help_text: str | None = None,
) -> None:
    """Render a precomputed value as a Streamlit metric."""
    options: dict[str, Any] = {}
    if delta is not None:
        options["delta"] = delta
    if help_text is not None:
        options["help"] = help_text

    st.metric(label=label, value=value, **options)
