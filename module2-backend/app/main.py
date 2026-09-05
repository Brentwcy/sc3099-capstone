from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    admin,
    audit,
    auth,
    checkins,
    courses,
    devices,
    enrollments,
    sessions,
    stats,
    users,
)
from app.core.config import get_settings
from app.core.database import database_is_ready
from app.core.rate_limit import redis_is_ready
from app.services.face_mock import close_face_service
from app.services.ip_geolocation import close_ip_country_resolver


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_face_service()
    await close_ip_country_resolver()


app = FastAPI(
    title=settings.app_name,
    description="Secure Attendance & Identity Verification System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Implemented API endpoints (all paths use the /api/v1 prefix):
#
# Authentication
#   POST   /auth/register
#   POST   /auth/login
#   POST   /auth/refresh
#   POST   /auth/logout
#
# Users
#   GET    /users/me
#   PUT    /users/me
#   GET    /users/
#   GET    /users/{user_id}
#   PATCH  /users/{user_id}
#
# Check-ins
#   POST   /checkins/
#   GET    /checkins/
#   GET    /checkins/my-checkins
#   GET    /checkins/flagged
#   GET    /checkins/session/{session_id}
#   GET    /checkins/{checkin_id}
#
# Devices
#   POST   /devices/register
#   GET    /devices/my-devices
#   GET    /devices/
#   GET    /devices/{device_id}
#   PATCH  /devices/{device_id}
#   DELETE /devices/{device_id}
#
# Courses
#   GET    /courses/
#   GET    /courses/{course_id}
#   POST   /courses/
#   PUT    /courses/{course_id}
#   DELETE /courses/{course_id}
#
# Enrollments
#   GET    /enrollments/my-enrollments
#   GET    /enrollments/course/{course_id}
#   POST   /enrollments/
#   POST   /enrollments/bulk
#   DELETE /enrollments/{enrollment_id}
#
# Sessions
#   GET    /sessions/
#   GET    /sessions/active
#   GET    /sessions/my-sessions
#   GET    /sessions/{session_id}
#   POST   /sessions/
#   PATCH  /sessions/{session_id}
#   DELETE /sessions/{session_id}
#
# Statistics and audit
#   GET    /stats/sessions/{session_id}
#   GET    /audit/
#
# Administrative test/setup endpoints
#   PATCH  /admin/users/{user_id}/deactivate
#   PATCH  /admin/users/{user_id}/activate
#   POST   /admin/users/bulk
#   PATCH  /admin/sessions/{session_id}/status
#   POST   /admin/enrollments/

for router in (
    auth.router,
    users.router,
    checkins.router,
    devices.router,
    courses.router,
    enrollments.router,
    sessions.router,
    stats.router,
    audit.router,
    admin.router,
):
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health_check() -> JSONResponse:
    database_ready = database_is_ready()
    redis_ready = redis_is_ready()
    healthy = database_ready and redis_ready
    payload = {
        "status": "healthy" if healthy else "unhealthy",
        "api": "healthy",
        "database": "healthy" if database_ready else "unavailable",
        "redis": "healthy" if redis_ready else "unavailable",
    }
    return JSONResponse(
        content=payload,
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
