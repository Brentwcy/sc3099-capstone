from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.schemas.user import (
    AdminUserUpdate,
    PaginatedUsers,
    UserProfileUpdate,
    UserResponse,
    UserSummary,
)
from app.schemas.face import UserFaceEnrollmentRequest
from app.services.audit import append_audit_log
from app.services.face_client import FaceServiceError, FaceServiceRejected
from app.services.face_mock import FaceService, get_face_service


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def read_profile(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.put("/me", response_model=UserResponse)
def update_profile(
    payload: UserProfileUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(current_user, field, value)
    append_audit_log(
        db,
        action="user_updated",
        request=request,
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        details={"changed_fields": sorted(changes)},
    )
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/face-enrollment", response_model=UserResponse)
async def enroll_current_user_face(
    payload: UserFaceEnrollmentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
) -> User:
    if not current_user.camera_consent:
        raise HTTPException(status_code=400, detail="Camera consent is required")

    try:
        result = await face_service.enroll_face(
            user_id=current_user.id,
            image=payload.image,
            camera_consent=current_user.camera_consent,
        )
    except FaceServiceRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except FaceServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    if not result.enrollment_successful:
        raise HTTPException(status_code=400, detail="Face enrollment was not successful")

    current_user.face_embedding_hash = result.face_template_hash
    current_user.face_enrolled = True
    append_audit_log(
        db,
        action="face_enrolled",
        request=request,
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        details={"quality_score": result.quality_score},
    )
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/", response_model=PaginatedUsers)
def list_users(
    role: UserRole | None = None,
    is_active: bool | None = None,
    search: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedUsers:
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active == is_active)
    if search:
        needle = f"%{search.strip().lower()}%"
        filters.append(or_(func.lower(User.email).like(needle), func.lower(User.full_name).like(needle)))

    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    users = db.scalars(
        select(User).where(*filters).order_by(User.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return PaginatedUsers(
        items=[UserSummary.model_validate(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.role != UserRole.admin:
        permitted = False
        if current_user.role == UserRole.instructor and user.role == UserRole.student:
            permitted = db.scalar(
                select(Enrollment.id)
                .join(Course, Course.id == Enrollment.course_id)
                .where(
                    Enrollment.student_id == user.id,
                    Enrollment.is_active.is_(True),
                    Course.is_active.is_(True),
                )
                .limit(1)
            ) is not None
        if not permitted:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(user, field, value)
    if changes.get("is_active") is True:
        user.failed_login_attempts = 0
        user.login_blocked_at = None
    append_audit_log(
        db,
        action="user_updated",
        request=request,
        user_id=admin.id,
        resource_type="user",
        resource_id=user.id,
        details={"changed_fields": sorted(changes)},
    )
    db.commit()
    db.refresh(user)
    return user
