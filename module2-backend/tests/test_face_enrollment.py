from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.face import FaceEnrollResult
from app.services.face_mock import get_face_service


def test_face_enrollment_requires_consent_and_persists_only_hash(
    client,
    db_session,
    student,
):
    student_user, student_headers = student

    missing_consent = client.post(
        "/api/v1/users/me/face-enrollment",
        headers=student_headers,
        json={"image": "test-image"},
    )
    assert missing_consent.status_code == 400

    consent = client.put(
        "/api/v1/users/me",
        headers=student_headers,
        json={"camera_consent": True, "geolocation_consent": True},
    )
    assert consent.status_code == 200

    class EnrollmentFaceService:
        async def enroll_face(self, *, user_id, image, camera_consent):
            assert user_id == student_user["id"]
            assert image == "test-image"
            assert camera_consent is True
            return FaceEnrollResult(
                enrollment_successful=True,
                face_template_hash="c" * 64,
                quality_score=0.93,
            )

    app.dependency_overrides[get_face_service] = lambda: EnrollmentFaceService()
    enrolled = client.post(
        "/api/v1/users/me/face-enrollment",
        headers=student_headers,
        json={"image": "test-image"},
    )
    app.dependency_overrides.pop(get_face_service, None)

    assert enrolled.status_code == 200, enrolled.text
    assert enrolled.json()["face_enrolled"] is True
    persisted = db_session.get(User, student_user["id"])
    assert persisted.face_embedding_hash == "c" * 64
    audit = db_session.query(AuditLog).filter_by(action="face_enrolled").one()
    assert audit.user_id == student_user["id"]
    assert "test-image" not in (audit.details or "")


def test_default_face_mock_persists_hash_without_image_payload(
    client,
    db_session,
    student,
    caplog,
):
    student_user, student_headers = student
    image_marker = "week6-sensitive-face-payload-never-persist"
    consent = client.put(
        "/api/v1/users/me",
        headers=student_headers,
        json={"camera_consent": True},
    )
    assert consent.status_code == 200

    enrolled = client.post(
        "/api/v1/users/me/face-enrollment",
        headers=student_headers,
        json={"image": image_marker},
    )

    assert enrolled.status_code == 200, enrolled.text
    assert image_marker not in enrolled.text
    persisted = db_session.get(User, student_user["id"])
    assert persisted.face_enrolled is True
    assert len(persisted.face_embedding_hash) == 64
    assert set(persisted.face_embedding_hash) <= set("0123456789abcdef")
    for audit in db_session.query(AuditLog).all():
        for column in AuditLog.__table__.columns:
            assert image_marker not in str(getattr(audit, column.name) or "")
    assert image_marker not in caplog.text
