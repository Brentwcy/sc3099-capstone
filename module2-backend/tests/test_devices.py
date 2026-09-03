from app.models.audit_log import AuditLog
from app.models.device import Device


def register_device(
    client, headers, fingerprint="week5-device-fingerprint", **overrides
):
    payload = {
        "device_fingerprint": fingerprint,
        "device_name": "My Browser",
        "platform": "web",
        "browser": "Firefox",
        "public_key": "public-key-material-that-is-long-enough-for-validation",
    }
    payload.update(overrides)
    return client.post("/api/v1/devices/register", headers=headers, json=payload)


def create_second_student(client):
    payload = {
        "email": "device-second-student@example.com",
        "password": "testpassword123",
        "full_name": "Second Device Student",
        "role": "student",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    return response.json(), {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_device_registration_and_owner_listing(client, db_session, student):
    student_user, student_headers = student

    response = register_device(client, student_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["device_fingerprint"] == "week5-device-fingerprint"
    assert body["browser"] == "Firefox"
    assert body["is_trusted"] is False
    assert body["trust_score"] == "low"
    assert "public_key" not in body

    devices = client.get("/api/v1/devices/my-devices", headers=student_headers)
    assert devices.status_code == 200
    assert [item["id"] for item in devices.json()] == [body["id"]]

    stored = db_session.get(Device, body["id"])
    assert stored is not None
    assert stored.user_id == student_user["id"]
    assert stored.public_key.startswith("public-key-material")
    assert db_session.query(AuditLog).filter_by(action="device_registered").count() == 1

    duplicate = register_device(client, student_headers)
    assert duplicate.status_code == 400


def test_legacy_registration_without_public_key_is_untrusted(
    client, db_session, student
):
    _student_user, student_headers = student
    response = client.post(
        "/api/v1/devices/",
        headers=student_headers,
        json={
            "device_fingerprint": "legacy-week5-device",
            "device_name": "Legacy Browser",
            "platform": "web",
            "browser": "Chrome",
        },
    )
    assert response.status_code == 201, response.text
    stored = db_session.get(Device, response.json()["id"])
    assert stored is not None
    assert stored.public_key.startswith("unattested:")
    assert stored.is_trusted is False


def test_device_ownership_admin_trust_and_revocation(
    client, db_session, student, admin
):
    _student_user, student_headers = student
    _admin_user, admin_headers = admin
    _other_student, other_headers = create_second_student(client)
    device = register_device(client, student_headers).json()

    forbidden_read = client.get(
        f"/api/v1/devices/{device['id']}", headers=other_headers
    )
    assert forbidden_read.status_code == 403
    forbidden_trust = client.patch(
        f"/api/v1/devices/{device['id']}",
        headers=student_headers,
        json={"is_trusted": True},
    )
    assert forbidden_trust.status_code == 403

    trusted = client.patch(
        f"/api/v1/devices/{device['id']}",
        headers=admin_headers,
        json={"is_trusted": True},
    )
    assert trusted.status_code == 200, trusted.text
    assert trusted.json()["is_trusted"] is True
    assert trusted.json()["trust_score"] == "high"

    renamed = client.patch(
        f"/api/v1/devices/{device['id']}",
        headers=student_headers,
        json={"device_name": "Primary Laptop"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["device_name"] == "Primary Laptop"

    revoked = client.delete(f"/api/v1/devices/{device['id']}", headers=student_headers)
    assert revoked.status_code == 204
    stored = db_session.get(Device, device["id"])
    assert stored is not None
    assert stored.is_active is False
    assert stored.revoked_at is not None
    assert db_session.query(AuditLog).filter_by(action="device_revoked").count() == 1

    owner_reactivation = client.patch(
        f"/api/v1/devices/{device['id']}",
        headers=student_headers,
        json={"is_active": True},
    )
    assert owner_reactivation.status_code == 403

    admin_reactivation = client.patch(
        f"/api/v1/devices/{device['id']}",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert admin_reactivation.status_code == 200
    assert admin_reactivation.json()["is_active"] is True


def test_cross_account_fingerprint_reuse_is_blocked_and_audited(
    client, db_session, student
):
    _student_user, student_headers = student
    other_student, other_headers = create_second_student(client)
    first = register_device(
        client, student_headers, fingerprint="shared-week5-fingerprint"
    )
    assert first.status_code == 201

    reused = register_device(
        client, other_headers, fingerprint="shared-week5-fingerprint"
    )
    assert reused.status_code == 409
    assert "another account" in reused.json()["detail"]
    assert (
        db_session.query(Device)
        .filter_by(device_fingerprint="shared-week5-fingerprint")
        .count()
        == 1
    )

    violation = db_session.query(AuditLog).filter_by(action="security_violation").one()
    assert violation.user_id == other_student["id"]
    assert violation.success is False


def test_admin_can_filter_all_devices(client, student, admin):
    student_user, student_headers = student
    _admin_user, admin_headers = admin
    registered = register_device(client, student_headers)
    assert registered.status_code == 201

    response = client.get(
        "/api/v1/devices/",
        headers=admin_headers,
        params={"user_id": student_user["id"], "is_active": True},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == registered.json()["id"]
    assert response.json()["limit"] == 50
    assert response.json()["offset"] == 0

    assert client.get("/api/v1/devices/", headers=student_headers).status_code == 403
