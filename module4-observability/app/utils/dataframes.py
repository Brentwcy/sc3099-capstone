"""Reusable Pandas preparation helpers for dashboard data."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

import pandas as pd


MissingColumnPolicy = Literal["ignore", "raise"]


def _require_dataframe(dataframe: pd.DataFrame) -> None:
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("dataframe must be a pandas DataFrame")


def records_to_dataframe(records: list[Mapping[str, Any]]) -> pd.DataFrame:
    """Build a DataFrame from a list of mapping records without adding fields."""
    if not isinstance(records, list):
        raise TypeError("records must be a list of mappings")
    if any(not isinstance(record, Mapping) for record in records):
        raise TypeError("every record must be a mapping")

    return pd.DataFrame([dict(record) for record in records])


def convert_datetime_columns(
    dataframe: pd.DataFrame,
    columns: Sequence[str],
    *,
    missing: MissingColumnPolicy = "ignore",
) -> pd.DataFrame:
    """Return a copy with selected columns converted to UTC datetimes."""
    _require_dataframe(dataframe)
    if isinstance(columns, str) or not isinstance(columns, Sequence):
        raise TypeError("columns must be a sequence of column names")
    if any(not isinstance(column, str) for column in columns):
        raise TypeError("every datetime column name must be a string")
    if missing not in ("ignore", "raise"):
        raise ValueError("missing must be either 'ignore' or 'raise'")

    absent_columns = [column for column in columns if column not in dataframe.columns]
    if absent_columns and missing == "raise":
        raise KeyError(f"Missing datetime columns: {absent_columns}")

    result = dataframe.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_datetime(
                result[column],
                errors="coerce",
                utc=True,
            )
    return result


def fill_missing_values(
    dataframe: pd.DataFrame,
    replacements: Mapping[str, Any],
) -> pd.DataFrame:
    """Return a copy with missing values filled only in named columns."""
    _require_dataframe(dataframe)
    if not isinstance(replacements, Mapping):
        raise TypeError("replacements must be a mapping of columns to values")

    absent_columns = [column for column in replacements if column not in dataframe.columns]
    if absent_columns:
        raise KeyError(f"Missing replacement columns: {absent_columns}")

    result = dataframe.copy()
    for column, replacement in replacements.items():
        result[column] = result[column].fillna(replacement)
    return result


def sort_dataframe(
    dataframe: pd.DataFrame,
    by: str,
    *,
    ascending: bool = True,
) -> pd.DataFrame:
    """Return rows sorted by one required column without changing the input."""
    _require_dataframe(dataframe)
    if not isinstance(by, str):
        raise TypeError("sort column must be a string")
    if by not in dataframe.columns:
        raise KeyError(f"Missing sort column: {by}")

    return dataframe.sort_values(by=by, ascending=ascending).copy()


def filter_equals(
    dataframe: pd.DataFrame,
    column: str,
    value: Any,
) -> pd.DataFrame:
    """Return rows whose named column equals a caller-supplied value."""
    _require_dataframe(dataframe)
    if not isinstance(column, str):
        raise TypeError("filter column must be a string")
    if column not in dataframe.columns:
        raise KeyError(f"Missing filter column: {column}")

    return dataframe.loc[dataframe[column] == value].copy()
