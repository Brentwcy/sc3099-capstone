"""Tests for reusable Week 3 Pandas preparation helpers."""

from __future__ import annotations

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from tests.fakes import APP_DIR  # noqa: F401  (adds the app directory to sys.path)

from utils.dataframes import (  # noqa: E402
    convert_datetime_columns,
    fill_missing_values,
    filter_equals,
    records_to_dataframe,
    sort_dataframe,
)


class DataFrameCreationTests(unittest.TestCase):
    def test_empty_records_return_an_empty_dataframe(self) -> None:
        result = records_to_dataframe([])

        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)

    def test_records_preserve_expected_rows_and_columns(self) -> None:
        records = [
            {"id": "first", "status": "approved"},
            {"id": "second", "status": "pending"},
        ]

        result = records_to_dataframe(records)

        self.assertEqual(list(result.columns), ["id", "status"])
        self.assertEqual(result.to_dict("records"), records)

    def test_invalid_record_inputs_raise_clear_errors(self) -> None:
        with self.assertRaisesRegex(TypeError, "list of mappings"):
            records_to_dataframe({"id": "not-a-list"})  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "every record must be a mapping"):
            records_to_dataframe([{"id": "valid"}, "invalid"])  # type: ignore[list-item]


class DateTimeConversionTests(unittest.TestCase):
    def test_valid_datetime_is_converted_to_utc_and_other_data_is_preserved(self) -> None:
        dataframe = pd.DataFrame(
            [{"checked_in_at": "2026-09-03T10:30:00+08:00", "status": "approved"}]
        )

        result = convert_datetime_columns(dataframe, ["checked_in_at"])

        self.assertEqual(str(result["checked_in_at"].dtype), "datetime64[ns, UTC]")
        self.assertEqual(
            result.loc[0, "checked_in_at"],
            pd.Timestamp("2026-09-03T02:30:00Z"),
        )
        self.assertEqual(result.loc[0, "status"], "approved")
        self.assertEqual(dataframe.loc[0, "checked_in_at"], "2026-09-03T10:30:00+08:00")

    def test_invalid_datetime_becomes_nat(self) -> None:
        dataframe = pd.DataFrame([{"starts_at": "not-a-timestamp"}])

        result = convert_datetime_columns(dataframe, ["starts_at"])

        self.assertTrue(pd.isna(result.loc[0, "starts_at"]))

    def test_missing_datetime_columns_can_be_ignored_or_rejected(self) -> None:
        dataframe = pd.DataFrame([{"status": "approved"}])

        ignored = convert_datetime_columns(dataframe, ["missing_at"])

        assert_frame_equal(ignored, dataframe)
        self.assertIsNot(ignored, dataframe)
        with self.assertRaisesRegex(KeyError, "missing_at"):
            convert_datetime_columns(dataframe, ["missing_at"], missing="raise")


class MissingValueTests(unittest.TestCase):
    def test_only_explicit_columns_receive_missing_value_replacements(self) -> None:
        dataframe = pd.DataFrame(
            [{"display_name": None, "risk_score": float("nan"), "status": "pending"}]
        )

        result = fill_missing_values(dataframe, {"display_name": "Unknown"})

        self.assertEqual(result.loc[0, "display_name"], "Unknown")
        self.assertTrue(pd.isna(result.loc[0, "risk_score"]))
        self.assertEqual(result.loc[0, "status"], "pending")
        self.assertIsNone(dataframe.loc[0, "display_name"])

    def test_missing_replacement_column_is_rejected(self) -> None:
        with self.assertRaisesRegex(KeyError, "display_name"):
            fill_missing_values(pd.DataFrame([{"status": "pending"}]), {"display_name": "Unknown"})


class SortingAndFilteringTests(unittest.TestCase):
    def test_sorting_supports_ascending_and_descending_without_mutation(self) -> None:
        dataframe = pd.DataFrame([{"score": 2}, {"score": 1}, {"score": 3}])

        ascending = sort_dataframe(dataframe, "score")
        descending = sort_dataframe(dataframe, "score", ascending=False)

        self.assertEqual(ascending["score"].tolist(), [1, 2, 3])
        self.assertEqual(descending["score"].tolist(), [3, 2, 1])
        self.assertEqual(dataframe["score"].tolist(), [2, 1, 3])

    def test_empty_dataframe_with_sort_column_is_supported(self) -> None:
        result = sort_dataframe(pd.DataFrame(columns=["score"]), "score")

        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), ["score"])

    def test_sorting_by_a_missing_column_is_rejected(self) -> None:
        with self.assertRaisesRegex(KeyError, "missing"):
            sort_dataframe(pd.DataFrame([{"score": 1}]), "missing")

    def test_equality_filter_returns_matching_rows_and_preserves_input(self) -> None:
        dataframe = pd.DataFrame(
            [
                {"id": "first", "status": "approved"},
                {"id": "second", "status": "pending"},
                {"id": "third", "status": "approved"},
            ]
        )

        result = filter_equals(dataframe, "status", "approved")

        self.assertEqual(result["id"].tolist(), ["first", "third"])
        self.assertEqual(len(dataframe), 3)

    def test_filtering_by_a_missing_column_is_rejected(self) -> None:
        with self.assertRaisesRegex(KeyError, "missing"):
            filter_equals(pd.DataFrame([{"status": "approved"}]), "missing", "value")


class DataFrameInputValidationTests(unittest.TestCase):
    def test_dataframe_helpers_reject_non_dataframe_inputs(self) -> None:
        invalid = None
        cases = (
            lambda: convert_datetime_columns(invalid, ["created_at"]),
            lambda: fill_missing_values(invalid, {}),
            lambda: sort_dataframe(invalid, "id"),
            lambda: filter_equals(invalid, "status", "approved"),
        )

        for operation in cases:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(TypeError, "pandas DataFrame"):
                    operation()


if __name__ == "__main__":
    unittest.main()
