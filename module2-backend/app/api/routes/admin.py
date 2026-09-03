from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models.session import AttendanceSession, SessionStatus
from app.models.user import User
from app.schemas.enrollment import EnrollmentCreate, EnrollmentResponse
from app.schemas.session import AdminSessionStatusUpdate
from app.schemas.user import UserCreate, UserSummary
from app.services.audit import append_audit_log
from app.services.enrollment import create_or_reactivate_enrollment


router = APIRouter(prefix="/admin", tags=["Admin"])


def set_active_state(
    *, user_id: str, active: bool, request: Request, admin: User, db: Session
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = active
    append_audit_log(
        db,
        action="user_updated",
        request=request,
        user_id=admin.id,
        resource_type="user",
        resource_id=user.id,
        details={"is_active": active},
    )
    db.commit()
    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "message": f"User {'activated' if active else 'deactivated'} successfully",
    }


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return set_active_state(user_id=user_id, active=False, request=request, admin=admin, db=db)


@router.patch("/users/{user_id}/activate")
def activate_user(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return set_active_state(user_id=user_id, active=True, request=request, admin=admin, db=db)


class BulkUsersRequest(BaseModel):
    users: list[UserCreate] = Field(min_length=1, max_length=100)


@router.post("/users/bulk", status_code=status.HTTP_201_CREATED)
def bulk_create_users(
    payload: BulkUsersRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    created: list[UserSummary] = []
    errors: list[dict[str, str]] = []
    for item in payload.users:
        email = str(item.email)
        if db.scalar(select(User.id).where(User.email == email)):
            errors.append({"email": email, "detail": "Email already registered"})
            continue
        user = User(
            email=email,
            full_name=item.full_name,
            hashed_password=hash_password(item.password),
            role=item.role,
        )
        db.add(user)
        db.flush()
        append_audit_log(
            db,
            action="user_created",
            request=request,
            user_id=admin.id,
            resource_type="user",
            resource_id=user.id,
            details={"created_user_id": user.id},
        )
        created.append(UserSummary.model_validate(user))
    db.commit()
    return {
        "created": len(created),
        "failed": len(errors),
        "users": [user.model_dump(mode="json") for user in created],
        "errors": errors,
    }


@router.patch("/sessions/{session_id}/status")
def set_session_status(
    session_id: str,
    payload: AdminSessionStatusUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(AttendanceSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    previous = session.status
    now = datetime.now(timezone.utc)
    session.status = payload.status
    if payload.status == SessionStatus.active and session.actual_start is None:
        session.actual_start = now
    if payload.status in {SessionStatus.closed, SessionStatus.cancelled}:
        session.actual_end = now
    append_audit_log(
        db,
        action="session_status_changed",
        request=request,
        user_id=admin.id,
        resource_type="session",
        resource_id=session.id,
        details={"from": previous.value, "to": payload.status.value, "admin_override": True},
    )
    db.commit()
    return {
        "id": session.id,
        "name": session.name,
        "status": session.status.value,
        "message": f"Session status changed from '{previous.value}' to '{session.status.value}'",
    }


@router.post(
    "/enrollments/",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_enrollment(
    payload: EnrollmentCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EnrollmentResponse:
    enrollment = create_or_reactivate_enrollment(
        db,
        student_id=payload.student_id,
        course_id=payload.course_id,
    )
    db.flush()
    append_audit_log(
        db,
        action="enrollment_created",
        request=request,
        user_id=admin.id,
        resource_type="enrollment",
        resource_id=enrollment.id,
        details={
            "course_id": enrollment.course_id,
            "student_id": enrollment.student_id,
            "admin_override": True,
        },
    )
    db.commit()
    db.refresh(enrollment)
    return EnrollmentResponse(
        id=enrollment.id,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
        is_active=enrollment.is_active,
        enrolled_at=enrollment.enrolled_at,
        dropped_at=enrollment.dropped_at,
    )
