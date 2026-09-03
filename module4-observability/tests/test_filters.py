"""Tests for reusable Week 3 Streamlit filter widgets."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import patch

from tests.fakes import fake_streamlit

from components.filters import (  # noqa: E402
    FilterOption,
    render_course_filter,
    render_date_range_filter,
    render_session_filter,
    render_status_filter,
)


class LabeledFilterTests(unittest.TestCase):
    def test_course_options_are_deduplicated_sorted_and_not_mutated(self) -> None:
        options = [
            FilterOption("course-b", "Software Engineering"),
            FilterOption("course-a", "Capstone Project"),
            FilterOption("course-a", "Capstone Project"),
            FilterOption("course-copy", "Capstone Project"),
        ]
        original = list(options)
        selected = FilterOption("course-b", "Software Engineering")

        with patch.object(
            fake_streamlit,
            "selectbox",
            return_value=selected,
            create=True,
        ) as selectbox:
            result = render_course_filter(options, key="course")

        self.assertEqual(result, "course-b")
        self.assertEqual(options, original)
        call = selectbox.call_args
        self.assertEqual(call.args, ("Course",))
        self.assertEqual(
            call.kwargs["options"],
            (
                None,
                FilterOption("course-a", "Capstone Project"),
                FilterOption("course-b", "Software Engineering"),
            ),
        )
        self.assertEqual(call.kwargs["format_func"](None), "All courses")
        self.assertFalse(call.kwargs["disabled"])

    def test_session_filter_returns_selected_session_value(self) -> None:
        selected = FilterOption("session-2", "Week 2 Studio")

        with patch.object(
            fake_streamlit,
            "selectbox",
            return_value=selected,
            create=True,
        ) as selectbox:
            result = render_session_filter(
                [
                    FilterOption("session-2", "Week 2 Studio"),
                    FilterOption("session-1", "Week 1 Studio"),
                ],
                key="session",
            )

        self.assertEqual(result, "session-2")
        self.assertEqual(
            [option.label for option in selectbox.call_args.kwargs["options"][1:]],
            ["Week 1 Studio", "Week 2 Studio"],
        )

    def test_all_choice_returns_none(self) -> None:
        with patch.object(
            fake_streamlit,
            "selectbox",
            return_value=None,
            create=True,
        ):
            result = render_course_filter(
                [FilterOption("course-a", "Capstone Project")]
            )

        self.assertIsNone(result)

    def test_empty_options_render_disabled_all_choice(self) -> None:
        with patch.object(
            fake_streamlit,
            "selectbox",
            return_value=None,
            create=True,
        ) as selectbox:
            result = render_session_filter([])

        self.assertIsNone(result)
        self.assertEqual(selectbox.call_args.kwargs["options"], (None,))
        self.assertTrue(selectbox.call_args.kwargs["disabled"])


class StatusFilterTests(unittest.TestCase):
    def test_status_options_are_caller_supplied_unique_and_sorted(self) -> None:
        statuses = ["pending", "approved", "pending", "flagged"]
        original = list(statuses)
        selected = FilterOption("flagged", "flagged")

        with patch.object(
            fake_streamlit,
            "selectbox",
            return_value=selected,
            create=True,
        ) as selectbox:
            result = render_status_filter(statuses, key="status")

        self.assertEqual(result, "flagged")
        self.assertEqual(statuses, original)
        self.assertEqual(
            [option.value for option in selectbox.call_args.kwargs["options"][1:]],
            ["approved", "flagged", "pending"],
        )
        self.assertEqual(
            selectbox.call_args.kwargs["format_func"](None),
            "All statuses",
        )


class DateFilterTests(unittest.TestCase):
    def test_date_range_returns_date_values_without_applying_logic(self) -> None:
        start = date(2026, 9, 1)
        end_as_datetime = datetime(2026, 9, 30, 18, 45)

        with patch.object(
            fake_streamlit,
            "date_input",
            side_effect=[start, end_as_datetime],
            create=True,
        ) as date_input:
            result = render_date_range_filter(key_prefix="checkins")

        self.assertEqual(result, (start, date(2026, 9, 30)))
        self.assertEqual(date_input.call_count, 2)
        self.assertEqual(date_input.call_args_list[0].args, ("Start date",))
        self.assertEqual(date_input.call_args_list[0].kwargs["value"], None)
        self.assertEqual(date_input.call_args_list[0].kwargs["key"], "checkins_start")
        self.assertEqual(date_input.call_args_list[1].kwargs["key"], "checkins_end")

    def test_empty_date_bounds_return_no_filter_values(self) -> None:
        with patch.object(
            fake_streamlit,
            "date_input",
            side_effect=[None, None],
            create=True,
        ):
            result = render_date_range_filter()

        self.assertEqual(result, (None, None))


if __name__ == "__main__":
    unittest.main()
