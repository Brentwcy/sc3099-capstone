"""Reusable table rendering for prepared dashboard records."""

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from components.feedback import render_empty_state


def render_table(
    dataframe: pd.DataFrame,
    *,
    empty_message: str = "No records found.",
    column_config: Mapping[str, Any] | None = None,
    height: int | None = None,
) -> None:
    """Render a prepared DataFrame, or shared feedback when it is empty."""
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("dataframe must be a pandas DataFrame")

    if dataframe.empty:
        render_empty_state(empty_message)
        return

    options: dict[str, Any] = {
        "hide_index": True,
        "use_container_width": True,
    }
    if column_config is not None:
        options["column_config"] = column_config
    if height is not None:
        options["height"] = height

    st.dataframe(dataframe, **options)
