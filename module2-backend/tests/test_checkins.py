import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.audit_log import AuditLog
from app.models.checkin import CheckIn, CheckInStatus
from app.models.risk_signal import RiskSignal
from app.models.session import AttendanceSession
from app.models.user import User
from app.schemas.face import FaceVerifyResult
from app.main import app
from app.services.face_mock import LivenessResult, get_face_service
from app.services.ip_geolocation import IPCountryLookupError, get_ip_country_resolver


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
    assert item["session_type"] == "lecture"
    assert item["course_code"] == "HIST101"
    assert item["course_name"] == "Check-in History"
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
    signal = db_session.query(RiskSignal).one()
    assert signal.checkin_id == body["id"]
    assert signal.signal_type.value == "device_unknown"
    assert signal.weight == 0.15
    assert db_session.query(AuditLog).filter_by(action="checkin_attempted").count() == 1
    approved_audit = db_session.query(AuditLog).filter_by(action="checkin_approved").one()
    assert approved_audit.resource_id == body["id"]

    duplicate = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"]),
    )
    assert duplicate.status_code == 400
    assert duplicate.json() == {"detail": "Already checked in"}
    assert db_session.query(CheckIn).count() == 1
    assert db_session.query(RiskSignal).count() == 1
    assert db_session.query(AuditLog).filter_by(action="checkin_attempted").count() == 2
    assert db_session.query(AuditLog).filter_by(action="checkin_approved").count() == 1


def test_checkin_rejects_foreign_ip_and_non_singapore_gps(
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

    class StubCountryResolver:
        def __init__(self):
            self.lookups = []

        async def country_code(self, ip_address):
            self.lookups.append(ip_address)
            if ip_address == "1.1.1.1":
                raise IPCountryLookupError("lookup unavailable")
            return {"8.8.8.8": "US", "119.81.44.63": "SG"}[ip_address]

    resolver = StubCountryResolver()
    app.dependency_overrides[get_ip_country_resolver] = lambda: resolver

    foreign_ip = client.post(
        "/api/v1/checkins/",
        headers={**student_headers, "X-Forwarded-For": "8.8.8.8, 10.0.0.1"},
        json=checkin_payload(session["id"]),
    )
    assert foreign_ip.status_code == 403
    assert foreign_ip.json() == {
        "detail": "Check-ins are only permitted from Singapore"
    }
    assert resolver.lookups == ["8.8.8.8"]

    unverifiable_ip = client.post(
        "/api/v1/checkins/",
        headers={**student_headers, "X-Forwarded-For": "1.1.1.1"},
        json=checkin_payload(session["id"]),
    )
    assert unverifiable_ip.status_code == 403
    assert resolver.lookups == ["8.8.8.8", "1.1.1.1"]

    outside_singapore = client.post(
        "/api/v1/checkins/",
        headers={**student_headers, "X-Forwarded-For": "119.81.44.63"},
        json=checkin_payload(
            session["id"],
            latitude=40.7128,
            longitude=-74.006,
        ),
    )
    assert outside_singapore.status_code == 403
    # GPS rejection occurs before a public-IP lookup.
    assert resolver.lookups == ["8.8.8.8", "1.1.1.1"]

    singapore_ip = client.post(
        "/api/v1/checkins/",
        headers={**student_headers, "X-Forwarded-For": "119.81.44.63"},
        json=checkin_payload(session["id"]),
    )
    assert singapore_ip.status_code == 201, singapore_ip.text
    assert resolver.lookups == ["8.8.8.8", "1.1.1.1", "119.81.44.63"]
    assert db_session.query(CheckIn).count() == 1
    assert db_session.query(AuditLog).filter_by(action="checkin_attempted").count() == 4


def test_checkin_allows_private_forwarded_ip_without_country_lookup(
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

    class UnexpectedCountryResolver:
        async def country_code(self, _ip_address):
            raise AssertionError("Private IPs must not use public geolocation")

    app.dependency_overrides[get_ip_country_resolver] = (
        lambda: UnexpectedCountryResolver()
    )
    malformed = client.post(
        "/api/v1/checkins/",
        headers={**student_headers, "X-Forwarded-For": "not-an-ip"},
        json=checkin_payload(session["id"]),
    )
    assert malformed.status_code == 403

    response = client.post(
        "/api/v1/checkins/",
        headers={**student_headers, "X-Forwarded-For": "10.20.30.40, 8.8.8.8"},
        json=checkin_payload(session["id"]),
    )

    assert response.status_code == 201, response.text


def test_face_matching_uses_enrolled_template(
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
    persisted_student = db_session.get(User, student_user["id"])
    persisted_student.face_enrolled = True
    persisted_student.face_embedding_hash = "a" * 64
    persisted_session = db_session.get(AttendanceSession, session["id"])
    persisted_session.require_face_match = True
    db_session.commit()

    class MatchingFaceService:
        async def check_liveness(self, **_kwargs):
            return LivenessResult(
                liveness_passed=True,
                liveness_score=0.9,
                challenge_type="passive",
                face_embedding_hash="b" * 64,
            )

        async def verify_face(self, *, image, reference_template_hash):
            assert image == "base64-test-image"
            assert reference_template_hash == "a" * 64
            return FaceVerifyResult(
                match_passed=True,
                match_score=0.94,
                match_threshold=0.7,
                face_detected=True,
            )

    app.dependency_overrides[get_face_service] = lambda: MatchingFaceService()
    response = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(session["id"]),
    )
    app.dependency_overrides.pop(get_face_service, None)

    assert response.status_code == 201, response.text
    assert response.json()["face_match_passed"] is True
    assert response.json()["face_match_score"] == 0.94


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


def test_session_and_detail_queries_enforce_role_access(
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

    other_payload = {
        "email": "other-checkin-instructor@example.com",
        "password": "testpassword123",
        "full_name": "Other Check-in Instructor",
        "role": "instructor",
    }
    assert client.post("/api/v1/auth/register", json=other_payload).status_code == 201
    other_token = client.post(
        "/api/v1/auth/login",
        json={"email": other_payload["email"], "password": other_payload["password"]},
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

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
        headers=other_headers,
    ).status_code == 200
    assert client.get(
        f"/api/v1/checkins/{checkin_id}",
        headers=other_headers,
    ).status_code == 200
    assert client.get(
        f"/api/v1/checkins/session/{session['id']}",
        headers=student_headers,
    ).status_code == 403

    filtered = client.get(
        "/api/v1/checkins/",
        headers=instructor_headers,
        params={
            "session_id": session["id"],
            "status": "approved",
            "min_risk_score": 0.1,
            "max_risk_score": 0.2,
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == checkin_id
    assert filtered.json()["items"][0]["student_email"]
    assert client.get("/api/v1/checkins/", headers=other_headers).json()["total"] == 1
    assert client.get("/api/v1/checkins/", headers=student_headers).status_code == 403


def test_flagged_review_queue_is_paginated_role_scoped_and_actionable(
    client,
    db_session,
    student,
    instructor,
    ta,
    admin,
):
    student_user, student_headers = student
    instructor_user, instructor_headers = instructor
    _ta_user, ta_headers = ta
    _admin_user, admin_headers = admin
    course, first_session = create_checkin_setup(
        client,
        student_user=student_user,
        student_headers=student_headers,
        instructor_user=instructor_user,
        instructor_headers=instructor_headers,
        admin_headers=admin_headers,
        activate=False,
    )
    now = datetime.now(timezone.utc)
    additional_sessions = []
    for index in range(2):
        response = client.post(
            "/api/v1/sessions/",
            headers=instructor_headers,
            json={
                "course_id": course["id"],
                "name": f"Review Session {index + 2}",
                "scheduled_start": (now + timedelta(hours=index + 2)).isoformat(),
                "scheduled_end": (now + timedelta(hours=index + 3)).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        additional_sessions.append(response.json())

    risk_factors = json.dumps(
        [
            {
                "type": "geo_out_of_bounds",
                "severity": "high",
                "weight": 0.4,
                "confidence": 1.0,
            }
        ]
    )
    flagged = CheckIn(
        session_id=first_session["id"],
        student_id=student_user["id"],
        status=CheckInStatus.flagged,
        checked_in_at=now - timedelta(minutes=10),
        risk_score=0.72,
        risk_factors=risk_factors,
    )
    appealed = CheckIn(
        session_id=additional_sessions[0]["id"],
        student_id=student_user["id"],
        status=CheckInStatus.appealed,
        checked_in_at=now - timedelta(minutes=20),
        risk_score=0.81,
        risk_factors=risk_factors,
        reviewed_by_id=instructor_user["id"],
        reviewed_at=now - timedelta(minutes=5),
        review_notes="Initially rejected after review.",
        appeal_reason="The venue GPS reading was inaccurate.",
        appealed_at=now,
    )
    rejected = CheckIn(
        session_id=additional_sessions[1]["id"],
        student_id=student_user["id"],
        status=CheckInStatus.rejected,
        checked_in_at=now,
        risk_score=1.0,
    )
    db_session.add_all([flagged, appealed, rejected])
    db_session.commit()

    first_page = client.get(
        "/api/v1/checkins/flagged",
        headers=instructor_headers,
        params={"course_id": course["id"], "limit": 1, "offset": 0},
    )
    assert first_page.status_code == 200, first_page.text
    body = first_page.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == appealed.id
    assert item["session_name"] == additional_sessions[0]["name"]
    assert item["course_id"] == course["id"]
    assert item["course_code"] == course["code"]
    assert item["course_name"] == course["name"]
    assert item["student_id"] == student_user["id"]
    assert item["student_name"] == student_user["full_name"]
    assert item["student_email"] == student_user["email"]
    assert item["status"] == "appealed"
    assert item["risk_factors"][0]["type"] == "geo_out_of_bounds"
    assert item["reviewed_by_id"] == instructor_user["id"]
    assert item["review_notes"] == "Initially rejected after review."
    assert item["appeal_reason"] == "The venue GPS reading was inaccurate."
    assert item["appealed_at"] is not None
    assert "latitude" not in item
    assert "device_id" not in item
    assert "liveness_score" not in item

    second_page = client.get(
        "/api/v1/checkins/flagged",
        headers=ta_headers,
        params={"limit": 1, "offset": 1},
    )
    assert second_page.status_code == 200
    assert second_page.json()["items"][0]["id"] == flagged.id
    assert client.get(
        "/api/v1/checkins/flagged",
        headers=admin_headers,
        params={"session_id": rejected.session_id},
    ).json()["total"] == 0
    assert client.get(
        "/api/v1/checkins/flagged",
        headers=student_headers,
    ).status_code == 403


def test_reused_device_fingerprint_is_flagged_and_audited(
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
        "email": "week5-device-owner@example.com",
        "password": "testpassword123",
        "full_name": "Device Owner",
        "role": "student",
    }
    assert client.post("/api/v1/auth/register", json=other_payload).status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": other_payload["email"], "password": other_payload["password"]},
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {token}"}
    registered = client.post(
        "/api/v1/devices/register",
        headers=other_headers,
        json={
            "device_fingerprint": "cross-account-week5-device",
            "platform": "web",
            "public_key": "public-key-material-that-is-long-enough-for-validation",
        },
    )
    assert registered.status_code == 201, registered.text

    response = client.post(
        "/api/v1/checkins/",
        headers=student_headers,
        json=checkin_payload(
            session["id"], device_fingerprint="cross-account-week5-device"
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "flagged"
    anomaly = next(
        factor
        for factor in response.json()["risk_factors"]
        if factor["type"] == "pattern_anomaly"
    )
    assert anomaly["details"]["reason"] == "device_fingerprint_bound_to_another_account"
    assert response.json()["risk_score"] >= 0.5
    violation = db_session.query(AuditLog).filter_by(action="security_violation").one()
    assert violation.resource_id == response.json()["id"]
    assert violation.success is False


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
