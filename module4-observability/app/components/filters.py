"""Reusable Streamlit filter widgets for caller-provided options."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import streamlit as st


@dataclass(frozen=True)
class FilterOption:
    """A stable filter value and its user-facing label."""

    value: str
    label: str


def _normalized_options(options: Sequence[FilterOption]) -> list[FilterOption]:
    if isinstance(options, (str, bytes)) or not isinstance(options, Sequence):
        raise TypeError("options must be a sequence of FilterOption values")
    if any(not isinstance(option, FilterOption) for option in options):
        raise TypeError("every option must be a FilterOption")

    ordered = sorted(
        options,
        key=lambda option: (option.label.casefold(), option.label, option.value),
    )
    unique: list[FilterOption] = []
    seen_values: set[str] = set()
    seen_labels: set[str] = set()
    for option in ordered:
        display_label = option.label.casefold()
        if option.value in seen_values or display_label in seen_labels:
            continue
        unique.append(option)
        seen_values.add(option.value)
        seen_labels.add(display_label)
    return unique


def _render_option_filter(
    label: str,
    options: Sequence[FilterOption],
    *,
    key: str | None,
    all_label: str,
) -> str | None:
    normalized = _normalized_options(options)
    widget_options: tuple[FilterOption | None, ...] = (None, *normalized)
    selected = st.selectbox(
        label,
        options=widget_options,
        index=0,
        format_func=lambda option: all_label if option is None else option.label,
        key=key,
        disabled=not normalized,
    )
    return None if selected is None else selected.value


def render_course_filter(
    options: Sequence[FilterOption],
    *,
    label: str = "Course",
    key: str | None = None,
    all_label: str = "All courses",
) -> str | None:
    """Render caller-provided course choices and return the selected value."""
    return _render_option_filter(
        label,
        options,
        key=key,
        all_label=all_label,
    )


def render_session_filter(
    options: Sequence[FilterOption],
    *,
    label: str = "Session",
    key: str | None = None,
    all_label: str = "All sessions",
) -> str | None:
    """Render caller-provided session choices and return the selected value."""
    return _render_option_filter(
        label,
        options,
        key=key,
        all_label=all_label,
    )


def render_status_filter(
    statuses: Sequence[str],
    *,
    label: str = "Status",
    key: str | None = None,
    all_label: str = "All statuses",
) -> str | None:
    """Render caller-provided status choices and return the selected status."""
    if isinstance(statuses, (str, bytes)) or not isinstance(statuses, Sequence):
        raise TypeError("statuses must be a sequence of strings")
    if any(not isinstance(status, str) for status in statuses):
        raise TypeError("every status must be a string")

    options = [FilterOption(value=status, label=status) for status in statuses]
    return _render_option_filter(
        label,
        options,
        key=key,
        all_label=all_label,
    )


def _date_only(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError("date filter values must be dates or None")


def render_date_range_filter(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    start_label: str = "Start date",
    end_label: str = "End date",
    key_prefix: str = "date_filter",
) -> tuple[date | None, date | None]:
    """Render independent date bounds without applying date filtering."""
    selected_start = st.date_input(
        start_label,
        value=start_date,
        key=f"{key_prefix}_start",
    )
    selected_end = st.date_input(
        end_label,
        value=end_date,
        key=f"{key_prefix}_end",
    )
    return _date_only(selected_start), _date_only(selected_end)
