from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.rate_limit import get_rate_limiter
from app.main import app
from app.models.device import Device
from app.schemas.device import DeviceRegister, DeviceResponse


def create_course(client, headers, *, code=None):
    payload = {
        "code": code or f"CS{uuid4().hex[:6].upper()}",
        "name": "Secure Systems",
        "semester": "AY2026-27 Sem 1",
        "venue_latitude": 1.3483,
        "venue_longitude": 103.6831,
        "venue_name": "NTU LT1",
        "geofence_radius_meters": 100,
        "risk_threshold": 0.5,
    }
    response = client.post("/api/v1/courses/", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def session_payload(course_id):
    now = datetime.now(timezone.utc)
    return {
        "course_id": course_id,
        "name": "Lecture 1",
        "session_type": "lecture",
        "scheduled_start": (now + timedelta(hours=1)).isoformat(),
        "scheduled_end": (now + timedelta(hours=2)).isoformat(),
    }


def test_course_crud_role_filters_and_coordinate_validation(client, admin, instructor):
    _admin_user, admin_headers = admin
    _instructor_user, instructor_headers = instructor
    course = create_course(client, admin_headers)
    assert "instructor_id" not in course
    assert "instructor_name" not in course

    assert client.post(
        "/api/v1/courses/",
        headers=instructor_headers,
        json={"code": "NOAUTH", "name": "No", "semester": "AY2026-27 Sem 1"},
    ).status_code == 403
    assert client.post(
        "/api/v1/courses/",
        headers=admin_headers,
        json={
            "code": "BADCOORD",
            "name": "Bad Coordinates",
            "semester": "AY2026-27 Sem 1",
            "venue_latitude": 1.3,
        },
    ).status_code == 422

    listed = client.get("/api/v1/courses/", headers=instructor_headers)
    assert listed.status_code == 200
    assert course["id"] in {item["id"] for item in listed.json()["items"]}
    updated = client.put(
        f"/api/v1/courses/{course['id']}",
        headers=instructor_headers,
        json={"name": "Updated Secure Systems", "risk_threshold": 0.7},
    )
    assert updated.status_code == 200
    assert updated.json()["risk_threshold"] == 0.7
    deleted = client.delete(f"/api/v1/courses/{course['id']}", headers=admin_headers)
    assert deleted.status_code == 204


def test_duplicate_course_code_is_rejected(client, admin):
    _admin_user, headers = admin
    code = f"CS{uuid4().hex[:6].upper()}"
    create_course(client, headers, code=code)
    duplicate = client.post(
        "/api/v1/courses/",
        headers=headers,
        json={"code": code.lower(), "name": "Duplicate", "semester": "AY2026-27 Sem 1"},
    )
    assert duplicate.status_code == 400
    assert duplicate.json() == {"detail": "Course code already exists"}


def test_enrollment_lifecycle_and_course_authorization(client, student, instructor, admin):
    student_user, student_headers = student
    _instructor_user, instructor_headers = instructor
    _admin_user, admin_headers = admin
    course = create_course(client, admin_headers)

    enrolled = client.post(
        "/api/v1/admin/enrollments/",
        headers=admin_headers,
        json={"student_id": student_user["id"], "course_id": course["id"]},
    )
    assert enrolled.status_code == 201
    enrollment_id = enrolled.json()["id"]
    assert client.post(
        "/api/v1/enrollments/",
        headers=instructor_headers,
        json={"student_id": student_user["id"], "course_id": course["id"]},
    ).status_code == 400

    mine = client.get("/api/v1/enrollments/my-enrollments", headers=student_headers)
    assert mine.status_code == 200
    assert mine.json()[0]["course_code"] == course["code"]
    assert "instructor_name" not in mine.json()[0]
    roster = client.get(
        f"/api/v1/enrollments/course/{course['id']}", headers=instructor_headers
    )
    assert roster.status_code == 200
    assert roster.json()["students"][0]["student_id"] == student_user["id"]
    profile = client.get(f"/api/v1/users/{student_user['id']}", headers=instructor_headers)
    assert profile.status_code == 200

    removed = client.delete(f"/api/v1/enrollments/{enrollment_id}", headers=instructor_headers)
    assert removed.status_code == 204
    assert client.get("/api/v1/enrollments/my-enrollments", headers=student_headers).json() == []


def test_instructor_access_is_global_by_role(client, student, instructor, admin):
    student_user, _student_headers = student
    first_instructor, first_instructor_headers = instructor
    _admin_user, admin_headers = admin
    other_payload = {
        "email": "other-instructor@example.com",
        "password": "testpassword123",
        "full_name": "Other Instructor",
        "role": "instructor",
    }
    other = client.post("/api/v1/auth/register", json=other_payload).json()
    other_token = client.post(
        "/api/v1/auth/login",
        json={"email": other_payload["email"], "password": other_payload["password"]},
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    course = create_course(client, admin_headers)
    client.post(
        "/api/v1/admin/enrollments/",
        headers=admin_headers,
        json={"student_id": student_user["id"], "course_id": course["id"]},
    )

    assert client.get(
        f"/api/v1/enrollments/course/{course['id']}", headers=other_headers
    ).status_code == 200
    assert client.get(f"/api/v1/users/{student_user['id']}", headers=other_headers).status_code == 200
    created = client.post(
        "/api/v1/sessions/", headers=other_headers, json=session_payload(course["id"])
    )
    assert created.status_code == 201
    assert "instructor_id" not in created.json()
    listed = client.get("/api/v1/sessions/", headers=first_instructor_headers)
    assert listed.status_code == 200
    assert created.json()["id"] in {item["id"] for item in listed.json()["items"]}
    updated = client.patch(
        f"/api/v1/sessions/{created.json()['id']}",
        headers=first_instructor_headers,
        json={"name": "Updated by another instructor"},
    )
    assert updated.status_code == 200
    assert other["id"] != first_instructor["id"]


def test_ta_roster_access_is_read_only(client, student, ta, admin):
    student_user, _student_headers = student
    _ta_user, ta_headers = ta
    _admin_user, admin_headers = admin
    course = create_course(client, admin_headers)
    enrollment = client.post(
        "/api/v1/admin/enrollments/",
        headers=admin_headers,
        json={"student_id": student_user["id"], "course_id": course["id"]},
    )
    assert enrollment.status_code == 201
    assert client.get(
        f"/api/v1/enrollments/course/{course['id']}", headers=ta_headers
    ).status_code == 200
    assert client.delete(
        f"/api/v1/enrollments/{enrollment.json()['id']}", headers=ta_headers
    ).status_code == 403


def test_ta_can_discover_sessions_with_filters(client, ta, instructor, admin):
    _ta_user, ta_headers = ta
    instructor_user, instructor_headers = instructor
    _admin_user, admin_headers = admin
    course = create_course(client, admin_headers)
    created = client.post(
        "/api/v1/sessions/",
        headers=instructor_headers,
        json=session_payload(course["id"]),
    )
    assert created.status_code == 201, created.text

    discovered = client.get(
        "/api/v1/sessions/my-sessions",
        headers=ta_headers,
        params={"status": "scheduled", "upcoming": True, "limit": 10},
    )
    assert discovered.status_code == 200, discovered.text
    assert created.json()["id"] in {session["id"] for session in discovered.json()}

    excluded = client.get(
        "/api/v1/sessions/my-sessions",
        headers=ta_headers,
        params={"status": "closed"},
    )
    assert excluded.status_code == 200
    assert created.json()["id"] not in {session["id"] for session in excluded.json()}


def test_session_creation_and_transitions_are_role_based(client, instructor, admin):
    _instructor_user, instructor_headers = instructor
    _admin_user, admin_headers = admin
    course = create_course(client, admin_headers)
    created = client.post(
        "/api/v1/sessions/", headers=instructor_headers, json=session_payload(course["id"])
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "scheduled"
    assert "instructor_id" not in body
    assert body["venue_latitude"] == course["venue_latitude"]
    assert body["checkin_opens_at"] < body["scheduled_start"]

    activated = client.patch(
        f"/api/v1/sessions/{body['id']}",
        headers=instructor_headers,
        json={"status": "active"},
    )
    assert activated.status_code == 200
    assert activated.json()["actual_start"] is not None
    invalid = client.patch(
        f"/api/v1/sessions/{body['id']}",
        headers=instructor_headers,
        json={"status": "scheduled"},
    )
    assert invalid.status_code == 400
    closed = client.patch(
        f"/api/v1/sessions/{body['id']}",
        headers=instructor_headers,
        json={"status": "closed"},
    )
    assert closed.status_code == 200
    assert client.delete(
        f"/api/v1/sessions/{body['id']}", headers=instructor_headers
    ).status_code == 400


def test_active_session_listing_respects_checkin_window(client, instructor, admin):
    _instructor_user, instructor_headers = instructor
    _admin_user, admin_headers = admin
    course = create_course(client, admin_headers)
    payload = session_payload(course["id"])
    now = datetime.now(timezone.utc)
    payload["checkin_opens_at"] = (now - timedelta(minutes=5)).isoformat()
    payload["checkin_closes_at"] = (now + timedelta(minutes=5)).isoformat()
    created = client.post("/api/v1/sessions/", headers=instructor_headers, json=payload).json()
    activated = client.patch(
        f"/api/v1/admin/sessions/{created['id']}/status",
        headers=admin_headers,
        json={"status": "active"},
    )
    assert activated.status_code == 200

    active = client.get("/api/v1/sessions/active")
    assert active.status_code == 200
    assert created["id"] in {item["id"] for item in active.json()}


def test_invalid_session_times_and_student_session_creation_are_rejected(
    client, student, instructor, admin
):
    _student_user, student_headers = student
    _instructor_user, instructor_headers = instructor
    _admin_user, admin_headers = admin
    course = create_course(client, admin_headers)
    payload = session_payload(course["id"])
    payload["scheduled_end"] = payload["scheduled_start"]
    assert client.post(
        "/api/v1/sessions/", headers=instructor_headers, json=payload
    ).status_code == 422
    assert client.post(
        "/api/v1/sessions/", headers=student_headers, json=session_payload(course["id"])
    ).status_code == 403


def test_authenticated_api_rate_limit_is_enforced(client, student):
    _student_user, headers = student

    class LimitedApiRateLimiter:
        def consume(self, *, policy, identifier):
            return 120 if policy.name == "api" else None

    app.dependency_overrides[get_rate_limiter] = lambda: LimitedApiRateLimiter()
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
    assert response.headers["retry-after"] == "120"


def test_device_foundation_validates_input_and_excludes_sensitive_fields(
    client, db_session, student
):
    student_user, _headers = student
    registration = DeviceRegister(
        device_fingerprint="device-foundation-123",
        device_name="Primary Browser",
        platform="web",
        public_key="-----BEGIN PUBLIC KEY-----test-key-material-----END PUBLIC KEY-----",
    )
    device = Device(user_id=student_user["id"], **registration.model_dump())
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)

    response = DeviceResponse.model_validate(device).model_dump(mode="json")
    assert response["device_fingerprint"] == registration.device_fingerprint
    assert "public_key" not in response
    assert "attestation_token" not in response

    with pytest.raises(ValidationError):
        DeviceRegister(
            device_fingerprint="bad fingerprint",
            platform="web",
            public_key="x" * 32,
        )
