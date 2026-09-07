"""Focused tests for the Week 7 flagged-review workflow."""

from __future__ import annotations

import unittest
from contextlib import nullcontext
from unittest.mock import patch

from tests.fakes import fake_streamlit, set_authenticated

from pages import flagged_review


def review_item() -> dict[str, object]:
    return {
        "id": "checkin-1",
        "checked_in_at": "2026-09-07T09:00:00Z",
        "course_code": "CS3099",
        "course_name": "Capstone",
        "session_name": "Week 7 Review",
        "student_name": "Test Student",
        "student_email": "student@example.com",
        "status": "flagged",
        "risk_score": 0.72,
        "risk_factors": [
            {"type": "device_unknown", "severity": "medium", "weight": 0.15}
        ],
        "appeal_reason": None,
    }


class RecordingClient:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records
        self.queue_tokens: list[str] = []
        self.reviews: list[dict[str, str]] = []

    def get_flagged_checkins(self, access_token: str, *, limit: int):
        self.queue_tokens.append(access_token)
        return {"items": self.records, "total": len(self.records), "limit": limit, "offset": 0}

    def review_checkin(
        self,
        access_token: str,
        checkin_id: str,
        *,
        status: str,
        review_notes: str,
    ):
        self.reviews.append(
            {
                "access_token": access_token,
                "checkin_id": checkin_id,
                "status": status,
                "review_notes": review_notes,
            }
        )
        return {"id": checkin_id, "status": status}


class FlaggedReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_streamlit.reset()
        set_authenticated("instructor")

    def test_queue_validation_and_preparation(self) -> None:
        records = [review_item()]
        self.assertEqual(flagged_review._queue_items({"items": records}), records)
        queue = flagged_review._prepare_queue(records)
        self.assertEqual(list(queue["id"]), ["checkin-1"])
        self.assertEqual(str(queue["checked_in_at"].dtype), "datetime64[ns, UTC]")

        with self.assertRaisesRegex(Exception, "Invalid flagged review response"):
            flagged_review._queue_items({"items": "not-a-list"})

    def test_empty_queue_renders_without_a_decision_form(self) -> None:
        client = RecordingClient([])
        with (
            patch.object(flagged_review, "loading_state", return_value=nullcontext()),
            patch.object(flagged_review, "render_kpi") as render_kpi,
            patch.object(flagged_review, "render_empty_state") as empty_state,
            patch.object(fake_streamlit, "caption", create=True),
        ):
            flagged_review.render_flagged_review(
                {"full_name": "Test Instructor"},
                client=client,
            )

        self.assertEqual(client.queue_tokens, ["access-old"])
        render_kpi.assert_called_once_with("Awaiting Review", 0)
        empty_state.assert_called_once_with(
            "No flagged or appealed check-ins require review."
        )
        self.assertEqual(client.reviews, [])

    def test_approve_submission_records_notes_and_refreshes_queue(self) -> None:
        client = RecordingClient([review_item()])
        fake_streamlit.form_submitted = True
        with (
            patch.object(flagged_review, "loading_state", return_value=nullcontext()),
            patch.object(flagged_review, "render_kpi"),
            patch.object(flagged_review, "render_table"),
            patch.object(fake_streamlit, "caption", create=True),
            patch.object(fake_streamlit, "selectbox", return_value="checkin-1", create=True),
            patch.object(fake_streamlit, "radio", return_value="Approve", create=True),
            patch.object(
                fake_streamlit,
                "text_area",
                return_value="  Evidence checked.  ",
                create=True,
            ),
            patch.object(fake_streamlit, "write", create=True),
            patch.object(fake_streamlit, "success", create=True),
        ):
            flagged_review.render_flagged_review(
                {"full_name": "Test Instructor"},
                client=client,
            )

        self.assertEqual(
            client.reviews,
            [
                {
                    "access_token": "access-old",
                    "checkin_id": "checkin-1",
                    "status": "approved",
                    "review_notes": "Evidence checked.",
                }
            ],
        )
        self.assertEqual(fake_streamlit.rerun_count, 1)
        self.assertEqual(
            fake_streamlit.session_state["flagged_review_completed"],
            "Check-in checkin-1 was approved.",
        )


if __name__ == "__main__":
    unittest.main()
