# Module 2–Module 4 Contract

This Week 2 contract covers dashboard authentication and connectivity. Operational and analytics endpoints will be added in their scheduled weeks.

## Configuration

- Dashboard setting: `BACKEND_URL`, default `http://localhost:8000`.
- Every call uses the shared dashboard `APIClient` with a 3.05-second connect timeout and 15-second response timeout.
- The dashboard has no database connection and sends bearer tokens only in request headers.

## Login

`POST /api/v1/auth/login`

```json
{
  "email": "instructor@example.com",
  "password": "securepass123"
}
```

Success is `200` with `access_token`, `refresh_token`, `token_type: "bearer"`, and a `user` containing at least `id`, `email`, `full_name`, and `role`.

- `ta`, `instructor`, and `admin` may enter the dashboard.
- `student` receives a dashboard role-gate error and the newly issued access token is logged out and cleared.
- `401` is displayed as an invalid-credentials/session message.
- `403` is displayed as a role/account access message.
- Network failure and timeout use distinct, safe messages.

## Current User

`GET /api/v1/users/me` with `Authorization: Bearer <access_token>`.

The dashboard validates the current user before rendering protected navigation. A `401` clears local token state and returns the user to login. Backend unavailability preserves local state so a transient outage does not destroy the session.

## Optional Read Dependencies

These endpoints are available for dashboard integration but are not required for the authentication milestone:

- `GET /api/v1/courses/` requires a bearer token and returns a paginated object with `items`, `total`, `limit`, and `offset`.
- `GET /api/v1/sessions/` requires an instructor or admin bearer token and returns the same pagination envelope.
- `GET /api/v1/checkins/my-checkins` requires a student bearer token. It accepts optional `course_id` and `limit` query parameters and returns the student's check-in history as a list.

## Logout

`POST /api/v1/auth/logout` with the access token. Local access token, refresh token, and user state are cleared even if the backend is unavailable.

## Connectivity

`GET /health` returns at least `status` or `api`. The dashboard shows connected, timeout, unavailable, and indeterminate states explicitly.
