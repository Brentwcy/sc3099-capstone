from datetime import timedelta

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select

from app.core.rate_limit import RedisRateLimiter, RateLimitPolicy, get_rate_limiter
from app.core.security import create_token
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User


def test_registration_profile_and_consent_flow(client, student):
    user, headers = student

    profile = client.get("/api/v1/users/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == user["email"]
    assert profile.json()["camera_consent"] is False
    assert "hashed_password" not in profile.json()

    updated = client.put(
        "/api/v1/users/me",
        headers=headers,
        json={
            "full_name": "Updated Student",
            "camera_consent": True,
            "geolocation_consent": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated Student"
    assert updated.json()["camera_consent"] is True
    assert updated.json()["geolocation_consent"] is False


def test_duplicate_email_and_markup_are_rejected(client, student):
    user, headers = student
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": user["email"].upper(),
            "password": "testpassword123",
            "full_name": "Duplicate",
        },
    )
    assert duplicate.status_code == 400

    markup = client.put(
        "/api/v1/users/me",
        headers=headers,
        json={"full_name": "<script>alert(1)</script>"},
    )
    assert markup.status_code == 422


def test_tokens_have_distinct_types_and_invalid_token_is_unauthorized(client, student):
    user, _headers = student
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "testpassword123"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["access_token"] != body["refresh_token"]

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": body["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["token_type"] == "bearer"
    assert client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer invalid"}
    ).status_code == 401


def test_audit_events_are_recorded_and_admin_only(client, db_session, student, admin):
    student_user, student_headers = student
    _admin_user, admin_headers = admin

    client.post(
        "/api/v1/auth/login",
        json={"email": student_user["email"], "password": "wrongpassword"},
    )
    client.post("/api/v1/auth/logout", headers=student_headers)

    assert client.get("/api/v1/audit/", headers=student_headers).status_code == 403
    response = client.get("/api/v1/audit/", headers=admin_headers)
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert {"user_created", "login_success", "login_failed", "logout"} <= actions

    log = db_session.scalar(select(AuditLog).limit(1))
    log.action = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        db_session.commit()
    db_session.rollback()


def test_admin_user_setup_and_inactive_login(client, admin):
    _admin_user, headers = admin
    bulk = client.post(
        "/api/v1/admin/users/bulk",
        headers=headers,
        json={
            "users": [
                {
                    "email": "bulk1@example.com",
                    "password": "testpassword123",
                    "full_name": "Bulk One",
                    "role": "student",
                },
                {
                    "email": "bulk2@example.com",
                    "password": "testpassword123",
                    "full_name": "Bulk Two",
                    "role": "ta",
                },
            ]
        },
    )
    assert bulk.status_code == 201
    assert bulk.json()["created"] == 2
    user_id = bulk.json()["users"][0]["id"]

    deactivated = client.patch(f"/api/v1/admin/users/{user_id}/deactivate", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "bulk1@example.com", "password": "testpassword123"},
    )
    assert login.status_code == 403

    activated = client.patch(f"/api/v1/admin/users/{user_id}/activate", headers=headers)
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True


def test_password_is_bcrypt_hashed(client, db_session, student):
    user, _headers = student
    stored = db_session.scalar(select(User).where(User.id == user["id"]))
    assert stored.hashed_password.startswith(("$2a$", "$2b$", "$2y$"))
    assert int(stored.hashed_password.split("$")[2]) >= 10
    assert "testpassword123" not in stored.hashed_password


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "testpassword123", "full_name": "Student"},
        {"email": "weak@example.com", "password": "short", "full_name": "Student"},
        {"email": "blank@example.com", "password": "testpassword123", "full_name": "   "},
    ],
)
def test_registration_validation_returns_422(client, payload):
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_missing_invalid_and_expired_access_tokens_return_401(client, student):
    user, _headers = student
    expired_token = create_token(
        subject=user["id"],
        email=user["email"],
        role=user["role"],
        token_type="access",
        expires_delta=timedelta(seconds=-1),
    )

    responses = [
        client.get("/api/v1/users/me"),
        client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid"}),
        client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        ),
    ]
    assert [response.status_code for response in responses] == [401, 401, 401]
    assert all(response.headers.get("www-authenticate") == "Bearer" for response in responses)


def test_access_and_refresh_tokens_cannot_be_used_interchangeably(client, student):
    user, _headers = student
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "testpassword123"},
    )
    tokens = login.json()

    profile = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )
    assert profile.status_code == 401
    assert refresh.status_code == 401


def test_non_admin_receives_exact_403_for_admin_endpoint(client, student):
    _user, headers = student
    response = client.get("/api/v1/audit/", headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


def test_login_rate_limit_returns_exact_429_contract(client):
    payload = {"email": "missing@example.com", "password": "wrongpassword"}
    for _ in range(60):
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401

    limited = client.post("/api/v1/auth/login", json=payload)
    assert limited.status_code == 429
    assert limited.json() == {"detail": "Rate limit exceeded"}
    assert int(limited.headers["retry-after"]) > 0


def test_registration_rate_limit_returns_exact_429_contract(client):
    for index in range(10):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"limited-{index}@example.com",
                "password": "testpassword123",
                "full_name": f"Limited User {index}",
            },
        )
        assert response.status_code == 201

    limited = client.post(
        "/api/v1/auth/register",
        json={
            "email": "limited-final@example.com",
            "password": "testpassword123",
            "full_name": "Limited User Final",
        },
    )
    assert limited.status_code == 429
    assert limited.json() == {"detail": "Rate limit exceeded"}


def test_rate_limit_keys_do_not_expose_ip_addresses():
    class FakeRedis:
        def __init__(self):
            self.keys = []

        def eval(self, _script, _key_count, key, _window, _limit):
            self.keys.append(key)
            return -1

    redis = FakeRedis()
    limiter = RedisRateLimiter(redis)
    policy = RateLimitPolicy(name="test", limit=2, window_seconds=60)
    limiter.consume(policy=policy, identifier="192.0.2.1")
    limiter.consume(policy=policy, identifier="192.0.2.2")

    assert redis.keys[0] != redis.keys[1]
    assert "192.0.2.1" not in redis.keys[0]
    assert redis.keys[0].startswith("saiv:rate-limit:test:")


def test_rate_limit_backend_failure_returns_safe_503(client):
    class FailingRateLimiter:
        def consume(self, *, policy, identifier):
            raise RedisConnectionError("internal connection detail")

    app.dependency_overrides[get_rate_limiter] = lambda: FailingRateLimiter()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Rate limiting service unavailable"}
    assert "connection detail" not in response.text
