import base64
from pathlib import Path
from time import perf_counter
from uuid import uuid4


SAMPLE_IMAGES_DIR = Path(__file__).parent.parent / "sample_images"


def encoded_image(image_name):
    return base64.b64encode(
        (SAMPLE_IMAGES_DIR / image_name).read_bytes()
    ).decode("utf-8")


def timed_post(client, path, payload):
    started_at = perf_counter()
    response = client.post(path, json=payload)
    return response, perf_counter() - started_at


def test_face_health_latency_is_below_100_ms(face_client):
    face_client.get("/health")  # Exclude connection setup from steady-state latency.
    durations = []
    for _ in range(10):
        started_at = perf_counter()
        response = face_client.get("/health")
        durations.append(perf_counter() - started_at)
        assert response.status_code == 200

    assert max(durations) < 0.100, (
        f"Slowest /health request was {max(durations) * 1000:.1f} ms"
    )


def test_face_enrollment_latency_is_below_one_second(face_client):
    image = encoded_image("obama.jpg")
    durations = []
    for _ in range(3):
        response, duration = timed_post(
            face_client,
            "/face/enroll",
            {
                "user_id": f"latency-enrollment-{uuid4()}",
                "image": image,
                "camera_consent": True,
            },
        )
        durations.append(duration)
        assert response.status_code in {200, 201}, response.text

    assert max(durations) < 1.0, (
        f"Slowest /face/enroll request was {max(durations) * 1000:.1f} ms"
    )


def test_face_verification_latency_is_below_800_ms(face_client):
    image = encoded_image("obama.jpg")
    enrollment = face_client.post(
        "/face/enroll",
        json={
            "user_id": f"latency-verification-{uuid4()}",
            "image": image,
            "camera_consent": True,
        },
    )
    assert enrollment.status_code in {200, 201}, enrollment.text
    reference_hash = enrollment.json()["face_template_hash"]

    durations = []
    for _ in range(5):
        response, duration = timed_post(
            face_client,
            "/face/verify",
            {
                "image": image,
                "reference_template_hash": reference_hash,
            },
        )
        durations.append(duration)
        assert response.status_code == 200
        assert response.json()["match_passed"] is True

    assert max(durations) < 0.800, (
        f"Slowest /face/verify request was {max(durations) * 1000:.1f} ms"
    )


def test_liveness_latency_is_below_800_ms(face_client):
    image = encoded_image("obama.jpg")
    durations = []
    for _ in range(5):
        response, duration = timed_post(
            face_client,
            "/liveness/check",
            {
                "challenge_response": image,
                "challenge_type": "passive",
            },
        )
        durations.append(duration)
        assert response.status_code == 200

    assert max(durations) < 0.800, (
        f"Slowest /liveness/check request was {max(durations) * 1000:.1f} ms"
    )
