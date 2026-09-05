# Test Status

## Week 1–5 Baseline

| Scope | Command | Current result | Owner / next action |
|---|---|---|---|
| Backend focused | `cd module2-backend && PYTHONPATH=. .venv/bin/pytest tests -q` | 55 passed in 38.53s on 2026-09-05 | Maanya; peer review pending |
| Dashboard focused | `cd module4-observability && python3 -m pytest tests -q` | 9 passed | Maanya |
| Backend compile | `cd module2-backend && python3 -m compileall -q app tests` | Passed on 2026-09-05 | Maanya |
| Dashboard compile | `cd module4-observability && python3 -m compileall -q app tests` | Passed | Maanya |
| Selected public Week 1–2 HTTP slice | Authentication, users, consent, auth security, input validation, retention, auth/dashboard contracts | 32 passed; 29/29 points against the Docker/PostgreSQL backend | Maanya |
| Public Week 3 core HTTP slice | Four course/session functional tests | 4 passed; 8/8 points against Docker/PostgreSQL/Redis on 2026-08-21 | Maanya |
| Public Week 3 management HTTP slice | Three session-management tests and one enrollment-roster test | 4 passed; 4/4 points against Docker/PostgreSQL/Redis on 2026-08-21 | Maanya |
| Alembic lifecycle | Fresh SQLite upgrade through `20260905_0008`; downgrade to `20260904_0007`; re-upgrade; `alembic check` | Login-blocking migration passed the full cycle with no schema drift on 2026-09-05; PostgreSQL rehearsal still required | Maanya |
| Week 4 check-in acceptance | Atomic create, duplicate, inactive/non-enrolled/window/consent failures, Haversine/geofence, unknown device, lateness, mock liveness, detail/session authorization | Covered by focused suite; all passed on 2026-08-27 | Maanya; peer review pending |
| Week 5 backend acceptance | Device lifecycle/RBAC/reuse, Singapore-only GPS/IP enforcement, filtered and flagged-review check-in queries, attempt/outcome audits, risk persistence, session attendance summary, Module 3 client contract/timeouts/errors | 23 focused cases passed on 2026-09-05 | Maanya; Module 3 contract and backend peer review pending |
| Full public suite | `python3 -m pytest tests/public/ -v` | Week 3+ fixtures require course/session/check-in endpoints not yet scheduled | Both |
| Docker Week 1–2 backend stack | Build backend; start PostgreSQL, Redis, and backend; probe `/health`; exercise real Redis limiter | Passed on 2026-08-21; PostgreSQL and Redis healthy, migrations applied, `/health` returned `200`, limiter returned `[None, None, 60]` for a two-attempt policy | Maanya |

Update this table with exact counts after each integration run. Do not mark later-week public failures as Week 2 regressions.
