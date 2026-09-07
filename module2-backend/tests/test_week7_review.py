import json
from datetime import datetime, timezone

import pytest

from app.models.audit_log import AuditLog
from app.models.checkin import CheckIn, CheckInStatus
from tests.test_checkins import create_checkin_setup


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_reviewer_decision_is_atomic_audited_and_removed_from_queue(
    client,
    db_session,
    student,
    instructor,
    admin,
    decision,
):
    student_user, student_headers = student
    instructor_user, instructor_headers = instructor
    _admin_user, admin_headers = admin
    _course, session = create_checkin_setup(
        client,
        student_user=student_user,
        student_headers=student_headers,
        instructor_user=instructor_user,
        instructor_headers=instructor_headers,
        admin_headers=admin_headers,
        activate=False,
    )
    checkin = CheckIn(
        session_id=session["id"],
        student_id=student_user["id"],
        status=CheckInStatus.flagged,
        checked_in_at=datetime.now(timezone.utc),
        risk_score=0.72,
    )
    db_session.add(checkin)
    db_session.commit()

    response = client.post(
        f"/api/v1/checkins/{checkin.id}/review",
        headers=instructor_headers,
        json={
            "status": decision,
            "review_notes": "  Evidence was checked with the teaching team.  ",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "id": checkin.id,
        "status": decision,
        "reviewed_by_id": instructor_user["id"],
        "reviewed_at": body["reviewed_at"],
        "review_notes": "Evidence was checked with the teaching team.",
    }
    assert body["reviewed_at"] is not None

    db_session.refresh(checkin)
    assert checkin.status.value == decision
    assert checkin.reviewed_by_id == instructor_user["id"]
    assert checkin.review_notes == "Evidence was checked with the teaching team."

    audit = db_session.query(AuditLog).filter_by(
        action="checkin_reviewed",
        resource_id=checkin.id,
    ).one()
    assert audit.user_id == instructor_user["id"]
    assert json.loads(audit.details) == {
        "decision": decision,
        "previous_status": "flagged",
        "session_id": session["id"],
        "student_id": student_user["id"],
    }
    assert "Evidence was checked" not in audit.details

    queue = client.get("/api/v1/checkins/flagged", headers=instructor_headers)
    assert queue.status_code == 200
    assert queue.json()["total"] == 0


def test_review_accepts_appeals_and_ta_or_admin_roles(
    client,
    db_session,
    student,
    instructor,
    ta,
    admin,
):
    student_user, student_headers = student
    instructor_user, instructor_headers = instructor
    ta_user, ta_headers = ta
    admin_user, admin_headers = admin
    for reviewer, expected_reviewer in (
        (ta_headers, ta_user["id"]),
        (admin_headers, admin_user["id"]),
    ):
        _course, session = create_checkin_setup(
            client,
            student_user=student_user,
            student_headers=student_headers,
            instructor_user=instructor_user,
            instructor_headers=instructor_headers,
            admin_headers=admin_headers,
            activate=False,
        )
        checkin = CheckIn(
            session_id=session["id"],
            student_id=student_user["id"],
            status=CheckInStatus.appealed,
            checked_in_at=datetime.now(timezone.utc),
            risk_score=0.8,
            appeal_reason="Please reconsider this check-in.",
            appealed_at=datetime.now(timezone.utc),
        )
        db_session.add(checkin)
        db_session.commit()

        response = client.post(
            f"/api/v1/checkins/{checkin.id}/review",
            headers=reviewer,
            json={"status": "approved", "review_notes": "Appeal verified."},
        )
        assert response.status_code == 200, response.text
        assert response.json()["reviewed_by_id"] == expected_reviewer


def test_review_rejects_unauthorized_invalid_and_repeated_actions(
    client,
    db_session,
    student,
    instructor,
    admin,
):
    student_user, student_headers = student
    instructor_user, instructor_headers = instructor
    _admin_user, admin_headers = admin
    _course, session = create_checkin_setup(
        client,
        student_user=student_user,
        student_headers=student_headers,
        instructor_user=instructor_user,
        instructor_headers=instructor_headers,
        admin_headers=admin_headers,
        activate=False,
    )
    checkin = CheckIn(
        session_id=session["id"],
        student_id=student_user["id"],
        status=CheckInStatus.flagged,
        risk_score=0.7,
    )
    db_session.add(checkin)
    db_session.commit()
    path = f"/api/v1/checkins/{checkin.id}/review"

    assert client.post(
        path,
        headers=student_headers,
        json={"status": "approved", "review_notes": "Student decision."},
    ).status_code == 403
    assert client.post(
        path,
        headers=instructor_headers,
        json={"status": "flagged", "review_notes": "Invalid decision."},
    ).status_code == 422
    assert client.post(
        path,
        headers=instructor_headers,
        json={"status": "approved", "review_notes": "   "},
    ).status_code == 422

    first = client.post(
        path,
        headers=instructor_headers,
        json={"status": "approved", "review_notes": "Final decision."},
    )
    assert first.status_code == 200
    repeated = client.post(
        path,
        headers=instructor_headers,
        json={"status": "rejected", "review_notes": "Changed decision."},
    )
    assert repeated.status_code == 409
    assert repeated.json() == {
        "detail": "Only flagged or appealed check-ins can be reviewed"
    }
    assert db_session.query(AuditLog).filter_by(
        action="checkin_reviewed",
        resource_id=checkin.id,
    ).count() == 1

    missing = client.post(
        "/api/v1/checkins/missing-checkin/review",
        headers=instructor_headers,
        json={"status": "approved", "review_notes": "Not found."},
    )
    assert missing.status_code == 404
