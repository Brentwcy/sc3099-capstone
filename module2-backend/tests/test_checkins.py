from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.checkin import CheckIn, CheckInStatus
from app.models.risk_signal import RiskSignal
from app.models.session import AttendanceSession
from app.main import app
from app.services.face_mock import LivenessResult, get_face_service


def create_checkin_setup(
    client,
    *,
    student_user,
    student_headers,
    instructor_user,
    instructor_headers,
    admin_headers,
    activate=True,
    grant_consent=True,
):
    if grant_consent:
        consent = client.put(
            "/api/v1/users/me",
            headers=student_headers,
            json={"camera_consent": True, "geolocation_consent": True},
        )
        assert consent.status_code == 200, consent.text

    code = f"W4{uuid4().hex[:6].upper()}"
    course = client.post(
        "/api/v1/courses/",
        headers=admin_headers,
        json={
            "code": code,
            "name": "Week 4 Check-ins",
            "semester": "AY2026-27 Sem 1",
            "instructor_id": instructor_user["id"],
            "venue_latitude": 1.3483,
            "venue_longitude": 103.6831,
            "geofence_radius_meters": 100,
            "risk_threshold": 0.5,
        },
    )
    assert course.status_code == 201, course.text
    enrollment = client.post(
        "/api/v1/admin/enrollments/",
        headers=admin_headers,
        json={
            "student_id": student_user["id"],
            "course_id": course.json()["id"],
        },
    )
    assert enrollment.status_code == 201, enrollment.text

    now = datetime.now(timezone.utc)
    session = client.post(
        "/api/v1/sessions/",
        headers=instructor_headers,
        json={
            "course_id": course.json()["id"],
            "name": "Week 4 Lecture",
            "scheduled_start": (now + timedelta(minutes=5)).isoformat(),
            "scheduled_end": (now + timedelta(hours=1)).isoformat(),
            "checkin_opens_at": (now - timedelta(minutes=5)).isoformat(),
            "checkin_closes_at": (now + timedelta(minutes=30)).isoformat(),
        },
    )
    assert session.status_code == 201, session.text
    if activate:
        activated = client.patch(
            f"/api/v1/admin/sessions/{session.json()['id']}/status",
            headers=admin_headers,
            json={"status": "active"},
        )
        assert activated.status_code == 200, activated.text
    return course.json(), session.json()


def checkin_payload(session_id, **overrides):
    payload = {
        "session_id": session_id,
        "latitude": 1.3483,
        "longitude": 103.6831,
        "location_accuracy_meters": 10,
        "device_fingerprint": "unknown-device-week4",
        "liveness_challenge_response": "base64-test-image",
    }
    payload.update(overrides)
    return payload


def test_student_can_list_and_filter_own_checkins(
    client,
    db_session,
    student,
    instructor,
    admin,
):
    student_user, student_headers = student
    instructor_user, instructor_headers = instructor
    _admin_user, admin_headers = admin

    course = client.post(
        "/api/v1/courses/",
        headers=admin_headers,
        json={
            "code": "HIST101",
            "name": "Check-in History",
            "semester": "AY2026-27 Sem 1",
            "instructor_id": instructor_user["id"],
        },
    )
    assert course.status_code == 201, course.text

    now = datetime.now(timezone.utc)
    session = client.post(
        "/api/v1/sessions/",
        headers=instructor_headers,
        json={
            "course_id": course.json()["id"],
            "name": "History Lecture",
            "scheduled_start": (now + timedelta(hours=1)).isoformat(),
            "scheduled_end": (now + timedelta(hours=2)).isoformat(),
        },
    )
    assert session.status_code == 201, session.text

    checkin = CheckIn(
        session_id=session.json()["id"],
        student_id=student_user["id"],
        status=CheckInStatus.approved,
        checked_in_at=now,
        risk_score=0.15,
    )
    db_session.add(checkin)
    db_session.commit()

    response = client.get("/api/v1/checkins/my-checkins", headers=student_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    item = response.json()[0]
    assert item["id"] == checkin.id
    assert item["session_id"] == session.json()["id"]
    assert item["session_name"] == "History Lecture"
    assert item["course_code"] == "HIST101"
    assert item["status"] == "approved"
    assert datetime.fromisoformat(item["checked_in_at"].replace("Z", "+00:00")) == now
    assert item["risk_score"] == 0.15

    filtered = client.get(
        "/api/v1/checkins/my-checkins",
        headers=student_headers,
        params={"course_id": "not-this-course"},
    )
    assert filtered.status_code == 200
    assert filtered.json() == []


def test_my_checkins_requires_a_student_account(client, instructor):
    _instructor_user, instructor_headers = instructor

    assert client.get("/api/v1/checkins/my-checkins").status_code == 401
    assert (
        client.get(
            "/api/v1/checkins/my-checkins", headers=instructor_headers
        ).status_code
        == 403
    )


def test_atomic_checkin_uses_mock_and_persists_risk_signals(
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

    response = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["liveness_passed"] is True
    assert body["liveness_score"] == 0.92
    assert body["risk_score"] == 0.15
    assert body["risk_factors"][0]["type"] == "device_unknown"
    assert body["distance_from_venue_meters"] == 0
    assert db_session.query(CheckIn).count() == 1
    assert db_session.query(RiskSignal).count() == 1

    duplicate = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"]),
    )
    assert duplicate.status_code == 400
    assert duplicate.json() == {"detail": "Already checked in"}
    assert db_session.query(CheckIn).count() == 1
    assert db_session.query(RiskSignal).count() == 1


def test_checkin_validation_failures_leave_no_partial_records(
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
        grant_consent=False,
    )

    inactive = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"]),
    )
    assert inactive.status_code == 400
    assert inactive.json() == {"detail": "Session is not active"}

    client.patch(
        f"/api/v1/admin/sessions/{session['id']}/status",
        headers=admin_headers,
        json={"status": "active"},
    )
    missing_consent = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"]),
    )
    assert missing_consent.status_code == 400
    assert missing_consent.json() == {
        "detail": "Camera and geolocation consent are required"
    }
    assert db_session.query(CheckIn).count() == 0
    assert db_session.query(RiskSignal).count() == 0


def test_outside_geofence_and_failed_liveness_are_rejected(
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
    outside = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"], latitude=1.3583),
    )
    assert outside.status_code == 201, outside.text
    assert outside.json()["status"] == "rejected"
    assert "geo_out_of_bounds" in {
        factor["type"] for factor in outside.json()["risk_factors"]
    }

    second_course, second_session = create_checkin_setup(
        client,
        student_user=student_user,
        student_headers=student_headers,
        instructor_user=instructor_user,
        instructor_headers=instructor_headers,
        admin_headers=admin_headers,
    )
    assert second_course["id"] != _course["id"]

    class FailedLivenessService:
        async def check_liveness(self, **_kwargs):
            return LivenessResult(
                liveness_passed=False,
                liveness_score=0.1,
                challenge_type="passive",
            )

    app.dependency_overrides[get_face_service] = lambda: FailedLivenessService()
    failed_liveness = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(second_session["id"]),
    )
    app.dependency_overrides.pop(get_face_service, None)
    assert failed_liveness.status_code == 201, failed_liveness.text
    assert failed_liveness.json()["status"] == "rejected"
    assert "liveness_failed" in {
        factor["type"] for factor in failed_liveness.json()["risk_factors"]
    }
    assert db_session.query(CheckIn).count() == 2


def test_session_and_detail_queries_enforce_ownership(
    client,
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
    created = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"]),
    )
    checkin_id = created.json()["id"]

    detail = client.get(f"/api/v1/checkins/{checkin_id}", headers=student_headers)
    assert detail.status_code == 200
    assert detail.json()["student_id"] == student_user["id"]
    session_list = client.get(
        f"/api/v1/checkins/session/{session['id']}",
        headers=instructor_headers,
    )
    assert session_list.status_code == 200
    assert session_list.json()[0]["id"] == checkin_id
    assert client.get(
        f"/api/v1/checkins/session/{session['id']}",
        headers=student_headers,
    ).status_code == 403


def test_non_enrollment_closed_window_and_lateness(
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

    other_payload = {
        "email": "week4-unenrolled@example.com",
        "password": "testpassword123",
        "full_name": "Unenrolled Student",
        "role": "student",
    }
    assert client.post("/api/v1/auth/register", json=other_payload).status_code == 201
    other_token = client.post(
        "/api/v1/auth/login",
        json={
            "email": other_payload["email"],
            "password": other_payload["password"],
        },
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    non_enrolled = client.post(
        "/api/v1/checkins/",
        headers=other_headers,
        json=checkin_payload(session["id"]),
    )
    assert non_enrolled.status_code == 400
    assert non_enrolled.json() == {
        "detail": "Student is not enrolled in this course"
    }

    persisted_session = db_session.get(AttendanceSession, session["id"])
    now = datetime.now(timezone.utc)
    persisted_session.checkin_opens_at = now - timedelta(minutes=10)
    persisted_session.checkin_closes_at = now - timedelta(minutes=1)
    db_session.commit()
    closed_window = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"]),
    )
    assert closed_window.status_code == 400
    assert closed_window.json() == {"detail": "Check-in window is closed"}
    assert db_session.query(CheckIn).count() == 0

    _late_course, late_session = create_checkin_setup(
        client,
        student_user=student_user,
        student_headers=student_headers,
        instructor_user=instructor_user,
        instructor_headers=instructor_headers,
        admin_headers=admin_headers,
    )
    persisted_late_session = db_session.get(AttendanceSession, late_session["id"])
    persisted_late_session.scheduled_start = now - timedelta(minutes=1)
    db_session.commit()
    late = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(late_session["id"]),
    )
    assert late.status_code == 201, late.text
    assert "unusual_time" in {
        factor["type"] for factor in late.json()["risk_factors"]
    }
