import base64
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

import pytest


SAMPLE_IMAGES_DIR = Path(__file__).parent.parent / "sample_images"
CHECKIN_SAMPLE_COUNT = 10


def encoded_image(image_name: str) -> str:
    return base64.b64encode(
        (SAMPLE_IMAGES_DIR / image_name).read_bytes()
    ).decode("utf-8")


def percentile_nearest_rank(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def test_real_m2_m3_checkin_p95_is_below_two_seconds(
    http_client,
    face_client,
    test_course,
    test_enrollment,
    auth_headers_student,
    auth_headers_instructor,
    auth_headers_admin,
):
    """Measure the complete HTTP check-in path, including all M3 calls."""
    consent = http_client.put(
        "/api/v1/users/me",
        headers=auth_headers_student,
        json={"camera_consent": True, "geolocation_consent": True},
    )
    assert consent.status_code == 200, consent.text

    image = encoded_image("obama.jpg")
    enrollment = http_client.post(
        "/api/v1/users/me/face-enrollment",
        headers=auth_headers_student,
        json={"image": image},
    )
    assert enrollment.status_code == 200, enrollment.text
    assert enrollment.json()["face_enrolled"] is True

    now = datetime.now(timezone.utc)
    session_ids: list[str] = []
    for index in range(CHECKIN_SAMPLE_COUNT):
        session = http_client.post(
            "/api/v1/sessions/",
            headers=auth_headers_instructor,
            json={
                "course_id": test_course["id"],
                "name": f"Week 6 latency sample {index + 1}",
                "session_type": "lecture",
                "scheduled_start": (now + timedelta(minutes=5)).isoformat(),
                "scheduled_end": (now + timedelta(hours=2)).isoformat(),
                "checkin_opens_at": (now - timedelta(minutes=10)).isoformat(),
                "checkin_closes_at": (now + timedelta(minutes=30)).isoformat(),
                "venue_latitude": 1.3483,
                "venue_longitude": 103.6831,
                "venue_name": "NTU LT1",
                "geofence_radius_meters": 100.0,
                "require_liveness_check": True,
                "require_face_match": True,
                "risk_threshold": 0.5,
            },
        )
        assert session.status_code in {200, 201}, session.text
        session_id = session.json()["id"]
        activation = http_client.patch(
            f"/api/v1/admin/sessions/{session_id}/status",
            headers=auth_headers_admin,
            json={"status": "active"},
        )
        assert activation.status_code == 200, activation.text
        session_ids.append(session_id)

    durations: list[float] = []
    results: list[dict] = []
    for index, session_id in enumerate(session_ids):
        started_at = perf_counter()
        response = http_client.post(
            "/api/v1/checkins/",
            headers=auth_headers_student,
            json={
                "session_id": session_id,
                "latitude": 1.3483,
                "longitude": 103.6831,
                "location_accuracy_meters": 10.0,
                "device_fingerprint": f"week6latencydevice{index:02d}",
                "liveness_challenge_response": image,
            },
        )
        durations.append(perf_counter() - started_at)
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["liveness_passed"] is True, result
        assert result["face_match_passed"] is True, result
        results.append(result)

    biometric_response = face_client.post(
        "/risk/assess",
        json={
            "liveness_score": results[0]["liveness_score"],
            "face_match_score": results[0]["face_match_score"],
        },
    )
    assert biometric_response.status_code == 200, biometric_response.text
    expected_final_risk = round(
        0.50 * biometric_response.json()["risk_score"]
        + 0.20,  # Each sample intentionally uses an unknown device.
        4,
    )
    assert all(
        result["risk_score"] == pytest.approx(expected_final_risk)
        for result in results
    )

    p95 = percentile_nearest_rank(durations, 0.95)
    print(
        "WEEK6_CHECKIN_LATENCY_MS "
        f"samples={len(durations)} "
        f"min={min(durations) * 1000:.1f} "
        f"median={percentile_nearest_rank(durations, 0.50) * 1000:.1f} "
        f"p95={p95 * 1000:.1f} "
        f"max={max(durations) * 1000:.1f} "
        f"statuses={sorted({result['status'] for result in results})}"
    )
    assert p95 < 2.0, f"Check-in p95 was {p95 * 1000:.1f} ms"
