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
        json={"image": "data:image/jpeg;base64,test-image"},
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
            assert image == "data:image/jpeg;base64,test-image"
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
        json={"image": "data:image/jpeg;base64,test-image"},
    )
    app.dependency_overrides.pop(get_face_service, None)

    assert enrolled.status_code == 200, enrolled.text
    assert enrolled.json()["face_enrolled"] is True
    persisted = db_session.get(User, student_user["id"])
    assert persisted.face_embedding_hash == "c" * 64
    audit = db_session.query(AuditLog).filter_by(action="face_enrolled").one()
    assert audit.user_id == student_user["id"]
    assert "test-image" not in (audit.details or "")
