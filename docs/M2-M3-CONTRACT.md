# Module 2 to Module 3 Contract

**Status:** Week 6 candidate. Face-count behavior and Module 2 aggregation are
implemented; Module 3 biometric-only scoring and protected-template durability
still require Module 3 owner completion/review before the full contract is frozen.

## Transport and privacy

- Module 2 calls Module 3 over HTTP using JSON and `Content-Type: application/json`.
- Images are base64-encoded PNG or JPEG bytes without a data-URL prefix.
- Every image-bearing field is limited to 15,000,000 encoded characters at the
  service boundary.
- Images exist only in request memory. Module 2 must not persist them, place them in audit details, or include them in logs or errors.
- Module 2 reuses one async HTTP client. Connect timeout is 2 seconds and read/write timeout is 8 seconds.
- Module 2 makes no automatic retries for image-bearing POST requests, preventing accidental replay and duplicate enrollment.

## Health and latency targets

| Operation | Target |
|---|---:|
| `GET /health` | < 100 ms |
| `POST /liveness/check` | < 800 ms |
| `POST /face/verify` | < 800 ms |
| `POST /face/enroll` | < 1.0 s |
| Complete Module 2 check-in workflow | < 2.0 s p95 |

Docker probes `GET /health` on port 8001 every 10 seconds, with a 5-second
timeout, 3 retries, and a 10-second startup grace period for MediaPipe model
initialization. Latency measurements exclude initial client connection setup and
run only after the service reports healthy.

## Endpoints

### `POST /face/enroll`

Request fields: `user_id: string`, `image: string`, `camera_consent: boolean`.

Successful response (`200` or `201`):

```json
{
  "enrollment_successful": true,
  "face_template_hash": "64-character SHA-256 hex string",
  "quality_score": 0.85,
  "details": {}
}
```

`quality_score` is within 0–1. Module 2 persists only `face_template_hash`, never the image or an embedding.
A successful enrollment must include a lowercase 64-character SHA-256
`face_template_hash`; a missing or malformed hash is treated as a Module 3
contract failure rather than marking the user as enrolled.

Enrollment requires exactly one detected face. No face returns `400` with
`No face detected in submitted image`; multiple faces return `400` with
`Multiple faces detected in submitted image`.

### `POST /face/verify`

Request fields: `image: string`, `reference_template_hash: string`.

Successful response (`200`): `match_passed: boolean`, `match_score: number`
(0–1), `match_threshold: number` (0–1), `face_detected: boolean`,
`face_count: integer`, optional `failure_reason: string`, and optional
`current_template_hash: string`.

Verification is successful only when exactly one face is present. No face is a
semantic `200` failure with `face_detected: false`, `face_count: 0`, and
`failure_reason: "no_face"`. Multiple faces are a semantic `200` failure with
`face_detected: true`, `face_count >= 2`, and
`failure_reason: "multiple_faces"`. Both cases return `match_passed: false` and
`match_score: 0.0`, allowing Module 2 to persist a rejected check-in and its
privacy-safe risk reason.

### `POST /liveness/check`

Request fields: `challenge_response: string`, `challenge_type: string` (`passive` by default).

Successful response (`200`): `liveness_passed: boolean|null`, `liveness_score: number` (0–1), `liveness_threshold: number` (0–1, default 0.6), `challenge_type: string`, optional `face_embedding_hash: string`, and `details: object`.

Liveness also fails semantically when multiple faces are present. Its `details`
contains only `face_detected`, `face_count`, and
`failure_reason: "multiple_faces"` for that case.

## Error mapping

| Module 3 result | Module 2 behavior |
|---|---|
| `400` | Sanitized `400`; submitted image rejected |
| Connect/read/write timeout or network failure | Sanitized `503`; service unavailable or timed out |
| Module 3 `5xx` | Sanitized `503`; service unavailable |
| Unexpected HTTP status or malformed response | Sanitized `503`; contract failure |

Provider response bodies and image data are never forwarded. No retry is performed.

## Risk ownership and weights

`POST /risk/assess` is owned by Module 3 but accepts only the biometric inputs
`liveness_score` and `face_match_score`. Its biometric risk result is composed
of 50% face matching risk and 50% liveness risk. It must not add device,
geolocation, network, or time defaults.

Module 2 owns the final check-in risk aggregation:

| Signal | Final weight |
|---|---:|
| Module 3 biometric match and liveness | 50% |
| Device attestation | 20% |
| Geolocation / geofence validation | 15% |
| Network / anti-proxy | 15% |

The current Module 2 implementation and client request follow this split. The
live Module 3 implementation must still be changed by its owner from the old
multi-signal calculation before final score semantics can be accepted.

## Template lifecycle handoff

`face_template_hash` is a SHA-256 identifier for the quantized landmark vector;
it is not sufficient for approximate similarity matching by itself. Module 2
persists that identifier as `users.face_embedding_hash` and sends it back as
`reference_template_hash`.

Module 3 currently uses the identifier to look up a protected 128-character
SimHash in Redis. That entry has an approximately 24-hour TTL, so a Redis expiry
or restart can turn a valid, non-identical selfie into a false mismatch. Before
the contract is frozen, the Module 3 owner must define durable protected-template
storage and a privacy-safe missing-template response that requests recovery or
re-enrollment rather than reporting biometric fraud/mismatch.

## Readiness

Module 3 reports `200` from `/health` only after its face model initializes.
Docker starts Module 3 after Redis is healthy and starts Module 2 only after the
Module 3 health check passes. Redis may still fall back to the in-memory cache
after a runtime cache failure.

## Pending owner decisions

The following remain deliberately unfrozen: deployment of the agreed
biometric-only Module 3 calculation, canonical verification hash aliases, and
the durable lifecycle/error behavior of similarity templates across Redis
expiry or restart.

The no-face and multiple-face behavior above is frozen for the Week 6 integration.
