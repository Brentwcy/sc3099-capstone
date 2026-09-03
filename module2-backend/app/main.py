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


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_face_service()


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
