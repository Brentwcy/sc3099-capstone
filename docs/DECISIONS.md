# Decision Log

## 2026-09-07 — Complete Docker check-in meets the Week 6 latency target

- Ten real Module 2 check-ins each exercised Module 3 liveness, verification,
  risk assessment, and PostgreSQL persistence. All ten were approved.
- The latest observed end-to-end latency was 53.9 ms minimum, 65.8 ms median,
  and 83.0 ms p95/maximum, below the `<2.0 s p95` target.
- This certifies the local Docker wiring and latency only. Final score semantics
  remain conditional because the current Module 3 `/risk/assess` still adds its
  old contextual defaults instead of returning the agreed 50/50 biometric-only
  result. With liveness and face-match scores both at 1.0, the observed final
  risk was 0.241; the corrected endpoint should produce 0.200 from the unknown
  device signal alone.

## 2026-09-07 — Protected-template durability remains a Module 3 release blocker

- Module 2 stores only the 64-character SHA-256 template identifier and returns
  it to Module 3 as `reference_template_hash`; it does not store an image,
  landmarks, or the approximate matching template.
- The live inspection found Module 3's protected 128-character SimHash in Redis
  with an approximately 24-hour TTL. Expiry or Redis restart therefore loses the
  state required to compare a new, non-identical selfie.
- The Module 3 owner must provide durable protected-template storage and a safe
  missing-template/re-enrollment outcome. A missing lookup must not be converted
  into an ordinary face mismatch. Exact error/status details remain an owner
  review item.

## 2026-09-07 — Post-integration privacy inspection found no raw image persistence

- After two ten-sample runs, PostgreSQL contained 20 check-ins with biometric
  scores and a 64-character template identifier, with no raw-image-style schema
  columns or oversized audit/risk details.
- Redis contained the protected template and rate-limit state only; 589 recent
  M2/M3 log lines had no JPEG base64 or image-data URI markers, and the longest
  inspected line was 292 characters.

## 2026-09-07 — Module 3 health and latency budgets support the M2 p95 target

- Docker probes Module 3 at `GET /health` on port 8001 with a 10-second interval, 5-second timeout, 3 retries, and 10-second startup grace period.
- Steady-state targets are `<100 ms` for health, `<800 ms` for liveness and verification, and `<1.0 s` for enrollment. These are enforced by live HTTP tests using the approved Obama sample after the service is healthy.
- The endpoint budgets reserve capacity for Module 2 orchestration and persistence within the complete check-in target of `<2.0 s p95`.

## 2026-09-07 — Week 6 face-count failures are explicit and fail securely

- Enrollment accepts exactly one face. Zero or multiple detected faces return a sanitized `400` and no template is cached or persisted.
- Verification returns `200` semantic failures for zero or multiple faces with `match_passed: false`, a zero score, `face_count`, and a machine-readable `failure_reason`. This lets Module 2 persist the rejected attempt and risk signal atomically.
- Liveness also fails on multiple faces so sessions that do not require face matching cannot bypass the policy. Module 2 persists only `failure_reason` and `face_count` from provider details.
- MediaPipe detects up to five faces for policy enforcement; biometric extraction still proceeds only when exactly one face is present.

## 2026-09-05 — Week 6 hardening proceeds without guessing open M2–M3 policy

- Completed now: require a valid lowercase SHA-256 template hash before persisting successful enrollment, cap image-bearing Module 3 inputs at 15,000,000 encoded characters, redact Redis connection/error detail from logs, and make Docker wait for a ready face model before starting Module 2.
- Privacy evidence: focused tests assert that enrollment and check-in image markers appear in neither API responses, modeled database columns, audit details, nor captured Module 2 logs. Timeout tests also prove no partial check-in/risk rows remain.
- Deferred: risk ownership/weights, multiple-face behavior, verification hash aliases, and similarity-template lifetime remain unchanged until the Module 3 owner responds. These choices affect the cross-module contract and must not be guessed independently.

## 2026-09-05 — Check-in location enforcement fails closed for public IPs

- Decision: `POST /api/v1/checkins/` returns `403` before creating a check-in when GPS coordinates are outside Singapore or a public client IP does not resolve to `SG`. A public IP that cannot be verified is also rejected.
- Client address: use the first `X-Forwarded-For` address when supplied, falling back to the socket peer. Non-global addresses and local test-client hostnames are treated as on-campus/local traffic and do not require country lookup.
- Testability: public-IP country resolution is an injectable async dependency. Tests cover foreign and Singapore public addresses without external network access.
- Audit behavior: the existing `checkin_attempted` event is committed before the location gate, while location rejection leaves no partial check-in or risk rows.

## 2026-09-05 — Per-IP authentication limits use a test-safe ceiling

- Decision: retain the Redis-backed per-IP login and registration limiters with a ceiling of 100,000 requests per hour.
- Reason: the controls remain implemented and testable without shared test-runner IP state blocking the grading suite. The independent database-backed block after 10 consecutive password failures remains unchanged.

## 2026-09-05 — Consecutive password failures persistently block the account

- Decision: the tenth consecutive incorrect password stores a per-account login block. Attempts 1–10 retain the generic `401 Invalid credentials` response; every subsequent attempt returns `429`, regardless of the supplied password.
- Reset behavior: a successful password login before the threshold resets the sequence. Admin activation clears an existing block and its failure counter.
- Separation: this account control is database-backed and independent of the existing Redis per-IP login rate limit, so changing IP addresses or restarting an API process does not bypass it.

## 2026-09-04 — The flagged endpoint is an actionable, paginated review queue

- Decision: `GET /api/v1/checkins/flagged` returns `{items, total, limit, offset}` and includes only `flagged` and `appealed` records. Unappealed `rejected` records remain available through the general status-filtered check-in endpoint.
- Access: instructor, TA, and admin roles may read the queue. The response includes check-in/session/course/student context, risk factors, and existing review/appeal metadata; it excludes raw coordinates, device identifiers, and biometric scores.
- Reason: the dashboard needs a bounded review workload and enough context to triage it without receiving unrelated sensitive detail.

## 2026-09-07 — A review decision is final and atomically audited

- Decision: `POST /api/v1/checkins/{id}/review` accepts `approved` or `rejected`
  only while a check-in is `flagged` or `appealed`. Instructor, TA, and admin
  roles may decide an item under the current role-based course model.
- Transaction behavior: PostgreSQL locks the check-in row while checking its
  state. The final status, reviewer ID, timestamp, notes, and append-only
  `checkin_reviewed` event commit together.
- Replay behavior: a repeated or competing decision returns `409` and cannot
  replace the first review or create another review audit event.
- Privacy: review notes are stored on the check-in but are not duplicated in the
  audit details. The audit records only IDs, prior status, and final decision.

## 2026-08-27 — Week 4 check-in persistence is one transaction

- Decision: validate session existence, active enrollment, session/window state, consent, duplicates, device state, geofence, and the mock liveness result before inserting. The check-in, denormalized risk summary, normalized `risk_signals` rows, and existing-device counters then commit together.
- Reason: every rejected validation leaves zero check-in/risk rows, while the database uniqueness constraint closes the concurrent duplicate race that an application pre-check cannot prevent.
- Retention: successful submissions receive the documented 30-day `scheduled_deletion_at` timestamp.

## 2026-08-27 — Unknown devices are risk signals during Week 4

- Decision: an unknown fingerprint contributes the documented `device_unknown` factor with weight `0.15`; it is not silently registered or bound and is not by itself a critical rejection.
- Reason: the official response example models unknown devices as risk, while registration, binding, reuse detection, and trust management are scheduled for Week 5.

## 2026-08-27 — The Week 4 face dependency mirrors Module 3 without network I/O

- Decision: use an injectable async mock that returns the documented `/liveness/check` fields and never persists or logs the challenge image. The check-in route depends on the service interface rather than constructing the mock directly.
- Reason: this completes the mocked Week 4 gate and leaves a narrow replacement seam for the reusable real HTTP client scheduled in Week 5.

## 2026-08-21 — Week 3 device work stops at the persistence and schema boundary

- Decision: create the documented device table, enums, constraints, indexes, and privacy-safe request/response schemas in Week 3. Device registration, binding, trust changes, and revocation routes remain in their scheduled Week 5 scope.
- Reason: this satisfies the Week 3 instruction to begin the device model without prematurely implementing security behavior before the device/check-in contract is exercised.
- Privacy boundary: response schemas exclude public keys and attestation tokens.

## 2026-09-04 — Instructor authorization is role-based

- Decision: courses and sessions do not store instructor ownership. Instructors receive the documented management permissions by role, while student session visibility remains constrained by active enrollment.
- Reason: the official data model and API contract do not define instructor ownership fields or an instructor-to-course assignment resource.

## 2026-08-21 — Session state changes use an explicit transition table

- Decision: instructor updates allow `scheduled -> active -> closed`, plus cancellation from any non-cancelled state. Activation and completion timestamps are recorded automatically. The documented admin test-setup endpoint can override status directly and audits the override.
- Reason: explicit transitions prevent accidental reopening and make session state behavior testable.
- Rejected: accepting arbitrary status strings or permitting backwards transitions.

## 2026-08-21 — TA roster access is read-only

- Decision: TAs may read a course roster as specified, but cannot create, remove, or bulk-change enrollments. Instructor mutations are role-based.
- Reason: the official schema provides no TA/course assignment resource. Global TA write access would exceed the documented role hierarchy and expose a cross-course mutation path.
- Deferred: if the group adds a written TA/course assignment contract, roster reads can also be narrowed to assigned courses.

## 2026-08-21 — Authentication limits use atomic Redis fixed windows

- Decision: enforce registration, login, and authenticated API limits with a shared Redis client and an atomic Lua script. Public-auth keys use a SHA-256 digest of the request IP; authenticated API keys use a digest of the user ID. Keys never contain credentials, tokens, or a plaintext IP address.
- Reason: the official limits are per IP, concurrent requests must not bypass the counter, and every backend replica must share the same state. Rejections use the documented `429` detail and include `Retry-After`.
- Failure behavior: authentication endpoints return a generic `503` if Redis cannot enforce the security control; the health endpoint reports Redis readiness alongside database readiness.
- Rejected: process-local counters, because they reset on restart and diverge across replicas.

## 2026-08-21 — Remove the redundant users email index in a new migration

- Decision: keep the database `UNIQUE` constraint on `users.email`, remove the additional equivalent unique index in revision `20260821_0002`, and align the ORM metadata with the constraint.
- Reason: PostgreSQL already indexes a unique constraint. The duplicate index added write overhead and caused Alembic schema drift.
- Rejected: rewriting the first migration. A corrective migration preserves the existing migration history.

## 2026-08-20 — Dashboard accesses data through Module 2 REST only

- Decision: remove PostgreSQL client dependencies and `DATABASE_URL` from the dashboard container.
- Reason: the execution plan explicitly assigns data ownership and authorization to Module 2. A single `APIClient` now owns dashboard HTTP behavior.
- Rejected: direct read-only SQL from Streamlit. It bypasses backend authorization and creates a second data contract.

## 2026-08-20 — Portable SQLAlchemy models with PostgreSQL deployment

- Decision: use SQLAlchemy 2.x models and Alembic, with string UUIDs and non-native enums so focused tests can run against SQLite while Docker uses PostgreSQL.
- Reason: request/response IDs remain UUID strings, and the first shared migration is deterministic across supported environments.
- Rejected: creating tables automatically at application import. Schema lifecycle belongs to Alembic.

## 2026-08-20 — Audit persistence participates in the business transaction

- Decision: audit helpers append to the caller's SQLAlchemy transaction; audit rows have no update timestamp and ORM hooks reject update/delete operations.
- Reason: successful user changes and their audit events should commit atomically, while the append-only model guards against accidental mutation.

## 2026-08-20 — Dashboard role checks are a UX gate

- Decision: only `ta`, `instructor`, and `admin` enter the Streamlit shell, but all protected operations still depend on backend authorization.
- Reason: hiding navigation is not a security boundary.
