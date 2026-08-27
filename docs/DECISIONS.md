# Decision Log

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

## 2026-08-21 — Unassigned courses are claimed on the first instructor mutation

- Decision: admins may create a course without `instructor_id`. The first instructor who creates a session or enrollment for that unassigned course becomes its owner in the same database transaction. Owned courses reject mutations from other instructors.
- Reason: the official contract requires session creators to teach the course, while the official public fixtures create courses without an owner and then use an instructor. Atomic claiming satisfies both without weakening authorization on an already-owned course.
- Rejected: allowing every instructor to mutate every course.

## 2026-08-21 — Session state changes use an explicit transition table

- Decision: instructor updates allow `scheduled -> active -> closed`, plus cancellation from any non-cancelled state. Activation and completion timestamps are recorded automatically. The documented admin test-setup endpoint can override status directly and audits the override.
- Reason: explicit transitions prevent accidental reopening and make session state behavior testable.
- Rejected: accepting arbitrary status strings or permitting backwards transitions.

## 2026-08-21 — TA roster access is read-only

- Decision: TAs may read a course roster as specified, but cannot create, remove, or bulk-change enrollments. Instructor mutations remain course-owner scoped.
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
