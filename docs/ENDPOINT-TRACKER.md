# Endpoint Tracker

Statuses reflect the Week 1–4 Maanya scope as of 2026-08-27. Implementation and focused verification are complete; entries remain in review until the required peer review is recorded. Later-week endpoints remain outside this implementation.

| Area | Method and path | Roles | Request | Success | Errors | Audit event | Owner | Tests | Status |
|---|---|---|---|---|---|---|---|---|---|
| Auth | `POST /api/v1/auth/register` | Public | Email, password, full name, role | `201` user | `400`, `422`, `429`, `503` | `user_created` | Maanya | `test_registration_profile_and_consent_flow`, `test_registration_validation_returns_422`, `test_registration_rate_limit_returns_exact_429_contract`, public auth tests | Review |
| Auth | `POST /api/v1/auth/login` | Public | Email, password | `200` access/refresh tokens and user | `401`, `403`, `422`, `429`, `503` | `login_success`, `login_failed` | Maanya | `test_audit_events_are_recorded_and_admin_only`, `test_login_rate_limit_returns_exact_429_contract`, public auth tests | Review |
| Auth | `POST /api/v1/auth/refresh` | Public | Refresh token | `200` replacement pair | `401`, `403`, `422` | N/A | Maanya | `test_tokens_have_distinct_types_and_invalid_token_is_unauthorized`, `test_access_and_refresh_tokens_cannot_be_used_interchangeably` | Review |
| Auth | `POST /api/v1/auth/logout` | Authenticated | Bearer token | `200` message | `401`, `403` | `logout` | Maanya | `test_audit_events_are_recorded_and_admin_only` | Review |
| Users | `GET /api/v1/users/me` | Authenticated | Bearer token | `200` profile and consent state | `401`, `403` | N/A | Maanya | `test_registration_profile_and_consent_flow`, public user/privacy tests | Review |
| Users | `PUT /api/v1/users/me` | Authenticated | Name and/or consent booleans | `200` updated profile | `401`, `403`, `422` | `user_updated` | Maanya | `test_registration_profile_and_consent_flow`, `test_duplicate_email_and_markup_are_rejected` | Review |
| Users | `GET /api/v1/users/` | Admin | Filters, limit, offset | `200` paginated users | `401`, `403`, `422` | N/A | Maanya | Focused admin tests | Review |
| Users | `GET /api/v1/users/{user_id}` | Admin in Week 2 | User ID | `200` user | `401`, `403`, `404` | N/A | Maanya | Focused admin tests | Review |
| Users | `PATCH /api/v1/users/{user_id}` | Admin | Role and/or active state | `200` updated user | `401`, `403`, `404`, `422` | `user_updated` | Maanya | Focused admin tests | Review |
| Audit | `GET /api/v1/audit/` | Admin | Documented filters and paging | `200` paginated audit logs | `401`, `403`, `422` | N/A | Maanya | `test_audit_events_are_recorded_and_admin_only`, public security/privacy tests | Review |
| Admin | `PATCH /api/v1/admin/users/{id}/deactivate` | Admin | User ID | `200` state/message | `401`, `403`, `404` | `user_updated` | Maanya | `test_admin_user_setup_and_inactive_login` | Review |
| Admin | `PATCH /api/v1/admin/users/{id}/activate` | Admin | User ID | `200` state/message | `401`, `403`, `404` | `user_updated` | Maanya | `test_admin_user_setup_and_inactive_login` | Review |
| Admin | `POST /api/v1/admin/users/bulk` | Admin | 1–100 user registrations | `201` created/failed summary | `401`, `403`, `422` | `user_created` per created user | Maanya | `test_admin_user_setup_and_inactive_login` | Review |
| Courses | `GET /api/v1/courses/` | Authenticated | Active, semester, instructor, limit, offset filters | `200` paginated courses | `401`, `403`, `422`, `429` | N/A | Maanya | `test_course_crud_role_filters_and_coordinate_validation`, public course tests | Review |
| Courses | `GET /api/v1/courses/{course_id}` | Authenticated | Course ID | `200` full course | `401`, `404`, `429` | N/A | Maanya | Public course/detail contract tests | Review |
| Courses | `POST /api/v1/courses/` | Admin | Course metadata, owner, venue, security defaults | `201` course | `400`, `401`, `403`, `422`, `429` | `course_created` | Maanya | `test_duplicate_course_code_is_rejected`, public course-management tests | Review |
| Courses | `PUT /api/v1/courses/{course_id}` | Admin or owner | Partial course fields | `200` course | `400`, `401`, `403`, `404`, `422`, `429` | `course_updated` | Maanya | `test_course_crud_role_filters_and_coordinate_validation` | Review |
| Courses | `DELETE /api/v1/courses/{course_id}` | Admin | Course ID | `204` | `401`, `403`, `404`, `429` | `course_deleted` | Maanya | `test_course_crud_role_filters_and_coordinate_validation` | Review |
| Enrollments | `GET /api/v1/enrollments/my-enrollments` | Student | Bearer token | `200` enrollment list | `401`, `403`, `429` | N/A | Maanya | `test_enrollment_lifecycle_and_course_authorization`, public enrollment tests | Review |
| Enrollments | `GET /api/v1/enrollments/course/{course_id}` | Admin, owner, TA read-only | Course ID, active/search filters | `200` roster | `401`, `403`, `404`, `422`, `429` | N/A | Maanya | `test_ta_roster_access_is_read_only`, public enrollment tests | Review |
| Enrollments | `POST /api/v1/enrollments/` | Admin or owner | Student and course IDs | `201` enrollment | `400`, `401`, `403`, `404`, `422`, `429` | `enrollment_created` | Maanya | `test_enrollment_lifecycle_and_course_authorization` | Review |
| Enrollments | `POST /api/v1/enrollments/bulk` | Admin or owner | Course and student email list | `200` result summary | `400`, `401`, `403`, `404`, `422`, `429` | `enrollment_created` | Maanya | Focused enrollment tests | Review |
| Enrollments | `DELETE /api/v1/enrollments/{enrollment_id}` | Admin or owner | Enrollment ID | `204` | `401`, `403`, `404`, `429` | `enrollment_deleted` | Maanya | `test_enrollment_lifecycle_and_course_authorization`, `test_ta_roster_access_is_read_only` | Review |
| Sessions | `GET /api/v1/sessions/` | Instructor or admin | Status, course, instructor, dates, paging | `200` paginated sessions | `401`, `403`, `422`, `429` | N/A | Maanya | Public session-management tests | Review |
| Sessions | `GET /api/v1/sessions/active` | Public | Current time | `200` active/open session list | N/A | N/A | Maanya | `test_active_session_listing_respects_checkin_window`, public session tests | Review |
| Sessions | `GET /api/v1/sessions/my-sessions` | Authenticated | Status, upcoming, limit | `200` relevant session list | `401`, `403`, `422`, `429` | N/A | Maanya | Focused session tests | Review |
| Sessions | `GET /api/v1/sessions/{session_id}` | Authenticated | Session ID | `200` session detail | `401`, `404`, `429` | N/A | Maanya | Public session/detail contract tests | Review |
| Sessions | `POST /api/v1/sessions/` | Instructor | Course, schedule, check-in window, venue/security overrides | `201` scheduled session | `401`, `403`, `404`, `422`, `429` | `session_created` | Maanya | `test_unassigned_course_is_claimed_and_session_transitions_are_enforced`, public session tests | Review |
| Sessions | `PATCH /api/v1/sessions/{session_id}` | Session owner | Partial fields or valid status transition | `200` session | `400`, `401`, `403`, `404`, `422`, `429` | `session_updated` | Maanya | Session transition and public update tests | Review |
| Sessions | `DELETE /api/v1/sessions/{session_id}` | Session owner | Scheduled session ID | `204` | `400`, `401`, `403`, `404`, `429` | `session_deleted` | Maanya | Session lifecycle tests | Review |
| Check-ins | `POST /api/v1/checkins/` | Student | Session, coordinates/accuracy, device fingerprint, optional liveness/QR | `201` approved, flagged, or rejected result | `400`, `401`, `403`, `404`, `422`, `429` | Scheduled Week 5 | Maanya | `test_atomic_checkin_uses_mock_and_persists_risk_signals`, validation/geofence/liveness/lateness tests | Review |
| Check-ins | `GET /api/v1/checkins/my-checkins` | Student | Optional course and limit filters | `200` own check-in history | `401`, `403`, `422`, `429` | N/A | Maanya | `test_student_can_list_and_filter_own_checkins`, `test_my_checkins_requires_a_student_account` | Review |
| Check-ins | `GET /api/v1/checkins/session/{session_id}` | TA, owner instructor, admin | Session ID | `200` session check-in list | `401`, `403`, `404`, `429` | N/A | Maanya | `test_session_and_detail_queries_enforce_ownership` | Review |
| Check-ins | `GET /api/v1/checkins/{checkin_id}` | Owner student, TA, owner instructor, admin | Check-in ID | `200` full privacy-safe detail | `401`, `403`, `404`, `429` | N/A | Maanya | `test_session_and_detail_queries_enforce_ownership` | Review |
| Admin | `PATCH /api/v1/admin/sessions/{session_id}/status` | Admin | Test/setup status override | `200` state/message | `401`, `403`, `404`, `422`, `429` | `session_status_changed` | Maanya | `test_active_session_listing_respects_checkin_window`, public fixtures | Review |
| Admin | `POST /api/v1/admin/enrollments/` | Admin | Student and course IDs | `201` enrollment | `400`, `401`, `403`, `404`, `422`, `429` | `enrollment_created` | Maanya | Enrollment lifecycle and public fixtures | Review |

Notes:

- Instructor access to `GET /users/{user_id}` depends on Week 3 enrollment/course authorization and is intentionally not guessed here.
- Registration and login use Redis-backed fixed windows keyed by a SHA-256 digest of the request IP. Limits are 10 registrations/hour/IP and 60 logins/hour/IP; rejected attempts return `429` and `Retry-After`.
- The current official API and security specifications define JWT expiry but do not require a refresh-token store or server-side token revocation. Logout records the required immutable audit event; clients discard their local tokens.
- An instructor may atomically claim an unassigned course when performing the first instructor-owned mutation. Once assigned, cross-instructor access is denied.
- The specification defines TA roster reads but no TA/course assignment resource. TAs therefore receive the documented roster read permission only; all enrollment writes remain restricted to admins and the course instructor.
- Week 3 also establishes the `devices` model, constraints, migration, and request/response schemas. Device routes remain intentionally scheduled for Week 5 and are not marked as implemented here.
- Week 4 treats an unknown device as the documented `device_unknown` risk signal rather than registering it implicitly. Device registration, binding, and suspicious-reuse behavior remain in Week 5.
- Week 4 uses a dependency-injectable, contract-shaped Module 3 liveness mock. The reusable async HTTP client and real service integration remain in Weeks 5–6.
- Check-in attempt/outcome audit events are explicitly scheduled for Week 5 in `plan.md`; Week 4 keeps the check-in record and all associated risk-signal rows in one commit.
