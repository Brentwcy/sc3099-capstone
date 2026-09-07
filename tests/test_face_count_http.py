import base64
from io import BytesIO
from pathlib import Path

import pytest


Image = pytest.importorskip("PIL.Image")
ImageOps = pytest.importorskip("PIL.ImageOps")

SAMPLE_IMAGES_DIR = Path(__file__).parent.parent / "sample_images"


def encoded_image(image_name):
    return base64.b64encode(
        (SAMPLE_IMAGES_DIR / image_name).read_bytes()
    ).decode("utf-8")


def encoded_multiple_face_image():
    portraits = []
    for image_name in ("obama.jpg", "biden.jpg"):
        with Image.open(SAMPLE_IMAGES_DIR / image_name) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            crop_size = min(source.width, source.height)
            left = (source.width - crop_size) // 2
            upper_portrait = source.crop((left, 0, left + crop_size, crop_size))
            portraits.append(
                upper_portrait.resize((512, 512), Image.Resampling.LANCZOS)
            )

    canvas = Image.new("RGB", (1048, 512), "white")
    canvas.paste(portraits[0], (0, 0))
    canvas.paste(portraits[1], (536, 0))
    output = BytesIO()
    canvas.save(output, format="JPEG", quality=95)
    return base64.b64encode(output.getvalue()).decode("utf-8")


def test_real_multiple_face_image_is_rejected_for_enrollment(face_client):
    response = face_client.post(
        "/face/enroll",
        json={
            "user_id": "week6-multiple-face-enrollment",
            "image": encoded_multiple_face_image(),
            "camera_consent": True,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Multiple faces detected in submitted image"
    }


def test_real_multiple_face_image_is_a_verification_failure(face_client):
    enrollment = face_client.post(
        "/face/enroll",
        json={
            "user_id": "week6-multiple-face-verification",
            "image": encoded_image("obama.jpg"),
            "camera_consent": True,
        },
    )
    assert enrollment.status_code in {200, 201}, enrollment.text

    response = face_client.post(
        "/face/verify",
        json={
            "image": encoded_multiple_face_image(),
            "reference_template_hash": enrollment.json()["face_template_hash"],
        },
    )

    assert response.status_code == 200
    assert response.json()["match_passed"] is False
    assert response.json()["match_score"] == 0.0
    assert response.json()["face_detected"] is True
    assert response.json()["face_count"] >= 2
    assert response.json()["failure_reason"] == "multiple_faces"


def test_real_multiple_face_image_fails_liveness(face_client):
    response = face_client.post(
        "/liveness/check",
        json={
            "challenge_response": encoded_multiple_face_image(),
            "challenge_type": "passive",
        },
    )

    assert response.status_code == 200
    assert response.json()["liveness_passed"] is False
    assert response.json()["liveness_score"] == 0.0
    assert response.json()["details"]["face_count"] >= 2
    assert response.json()["details"]["failure_reason"] == "multiple_faces"
