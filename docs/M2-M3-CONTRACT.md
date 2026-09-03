# Module 2 to Module 3 Contract

**Status:** Week 5 candidate freeze. Module 3 owner review is required before marking this frozen.

## Transport and privacy

- Module 2 calls Module 3 over HTTP using JSON and `Content-Type: application/json`.
- Images are base64-encoded PNG or JPEG bytes without a data-URL prefix.
- Images exist only in request memory. Module 2 must not persist them, place them in audit details, or include them in logs or errors.
- Module 2 reuses one async HTTP client. Connect timeout is 2 seconds and read/write timeout is 8 seconds.
- Module 2 makes no automatic retries for image-bearing POST requests, preventing accidental replay and duplicate enrollment.

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

### `POST /face/verify`

Request fields: `image: string`, `reference_template_hash: string`.

Successful response (`200`): `match_passed: boolean`, `match_score: number` (0–1), `match_threshold: number` (0–1), `face_detected: boolean`, and optional `current_template_hash: string`.

### `POST /liveness/check`

Request fields: `challenge_response: string`, `challenge_type: string` (`passive` by default).

Successful response (`200`): `liveness_passed: boolean|null`, `liveness_score: number` (0–1), `liveness_threshold: number` (0–1, default 0.6), `challenge_type: string`, optional `face_embedding_hash: string`, and `details: object`.

## Error mapping

| Module 3 result | Module 2 behavior |
|---|---|
| `400` | Sanitized `400`; submitted image rejected |
| Connect/read/write timeout or network failure | Sanitized `503`; service unavailable or timed out |
| Module 3 `5xx` | Sanitized `503`; service unavailable |
| Unexpected HTTP status or malformed response | Sanitized `503`; contract failure |

Provider response bodies and image data are never forwarded. No retry is performed.

Current Module 3 behavior is more specific: enrollment returns `400` for an invalid image or no detected face, while verification and liveness return `200` with `face_detected: false` or `liveness_passed: false` and a zero score. Multiple-face handling is not explicit in the current Module 3 response and remains an open item for owner review before contract freeze.
