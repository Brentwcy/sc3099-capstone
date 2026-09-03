from app.models.checkin import CheckIn, CheckInStatus

from tests.test_checkins import create_checkin_setup


def test_session_attendance_summary_and_authorization(
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
    )
    persisted = CheckIn(
        session_id=session["id"],
        student_id=student_user["id"],
        status=CheckInStatus.approved,
        risk_score=0.2,
        distance_from_venue_meters=12.5,
    )
    db_session.add(persisted)
    db_session.commit()

    response = client.get(
        f"/api/v1/stats/sessions/{session['id']}", headers=instructor_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == session["id"]
    assert body["course_code"].startswith("W4")
    assert body["total_enrolled"] == 1
    assert body["checked_in"] == 1
    assert body["attendance_rate"] == 1.0
    assert body["by_status"]["approved"] == 1
    assert body["average_risk_score"] == 0.2
    assert body["average_distance_meters"] == 12.5
    assert body["risk_distribution"] == {"low": 1, "medium": 0, "high": 0}

    assert (
        client.get(
            f"/api/v1/stats/sessions/{session['id']}", headers=student_headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/stats/sessions/{session['id']}", headers=admin_headers
        ).status_code
        == 200
    )
