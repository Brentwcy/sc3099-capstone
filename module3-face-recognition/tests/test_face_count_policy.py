from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException

from app import face_engine as face_engine_module
from app import main
from app.face_engine import FaceEngine
from app.models import FaceEnrollRequest, FaceVerifyRequest, LivenessRequest


@pytest.fixture
def decoded_image(monkeypatch):
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    monkeypatch.setattr(main, "decode_base64_image", lambda _value: image)
    return image


def test_face_engine_returns_all_detected_faces(monkeypatch):
    detected_faces = [["first-face"], ["second-face"]]

    class Detector:
        def detect(self, _image):
            return SimpleNamespace(face_landmarks=detected_faces)

    engine = object.__new__(FaceEngine)
    engine.detector = Detector()
    monkeypatch.setattr(face_engine_module.mp, "Image", lambda **_kwargs: object())

    assert engine.extract_faces(np.zeros((2, 2, 3), dtype=np.uint8)) == detected_faces


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("faces", "detail"),
    [
        ([], "No face detected in submitted image"),
        ([[], []], "Multiple faces detected in submitted image"),
    ],
)
async def test_enrollment_rejects_non_single_face_capture(
    monkeypatch,
    decoded_image,
    faces,
    detail,
):
    monkeypatch.setattr(main.face_engine, "extract_faces", lambda _image: faces)

    with pytest.raises(HTTPException) as error:
        await main.enroll_face(
            FaceEnrollRequest(user_id="student", image="image", camera_consent=True)
        )

    assert error.value.status_code == 400
    assert error.value.detail == detail


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("faces", "face_detected", "face_count", "failure_reason"),
    [
        ([], False, 0, "no_face"),
        ([[], []], True, 2, "multiple_faces"),
    ],
)
async def test_verification_returns_semantic_failure_for_non_single_face_capture(
    monkeypatch,
    decoded_image,
    faces,
    face_detected,
    face_count,
    failure_reason,
):
    monkeypatch.setattr(main.face_engine, "extract_faces", lambda _image: faces)

    result = await main.verify_face(
        FaceVerifyRequest(image="image", reference_template_hash="a" * 64)
    )

    assert result.match_passed is False
    assert result.match_score == 0.0
    assert result.face_detected is face_detected
    assert result.face_count == face_count
    assert result.failure_reason == failure_reason


@pytest.mark.asyncio
async def test_liveness_rejects_multiple_faces_as_a_semantic_failure(
    monkeypatch,
    decoded_image,
):
    monkeypatch.setattr(
        main.face_engine,
        "extract_faces",
        lambda _image: [[], []],
    )

    result = await main.check_liveness(
        LivenessRequest(challenge_response="image", challenge_type="passive")
    )

    assert result.liveness_passed is False
    assert result.liveness_score == 0.0
    assert result.details == {
        "face_detected": True,
        "face_count": 2,
        "failure_reason": "multiple_faces",
    }
