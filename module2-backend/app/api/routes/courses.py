from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.models.course import Course
from app.models.user import User, UserRole
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate, PaginatedCourses
from app.services.audit import append_audit_log


router = APIRouter(prefix="/courses", tags=["Courses"])


def course_response(course: Course) -> CourseResponse:
    values = {column.name: getattr(course, column.name) for column in Course.__table__.columns}
    return CourseResponse(**values)


def validate_coordinate_pair(latitude: float | None, longitude: float | None) -> None:
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422,
            detail="Venue latitude and longitude must be provided together",
        )


@router.get("/", response_model=PaginatedCourses)
def list_courses(
    is_active: bool | None = True,
    semester: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedCourses:
    filters = []
    if is_active is not None:
        filters.append(Course.is_active == is_active)
    if semester is not None:
        filters.append(Course.semester == semester)
    total = db.scalar(select(func.count()).select_from(Course).where(*filters)) or 0
    courses = db.scalars(
        select(Course).where(*filters).order_by(Course.code).limit(limit).offset(offset)
    ).all()
    return PaginatedCourses(
        items=[course_response(course) for course in courses],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{course_id}", response_model=CourseResponse)
def read_course(
    course_id: str,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseResponse:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course_response(course)


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CourseResponse:
    course = Course(**payload.model_dump())
    db.add(course)
    try:
        db.flush()
        append_audit_log(
            db,
            action="course_created",
            request=request,
            user_id=admin.id,
            resource_type="course",
            resource_id=course.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Course code already exists") from None
    db.refresh(course)
    return course_response(course)


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: str,
    payload: CourseUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseResponse:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    if current_user.role not in {UserRole.admin, UserRole.instructor}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    changes = payload.model_dump(exclude_unset=True)
    if current_user.role != UserRole.admin and "is_active" in changes:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    latitude = changes.get("venue_latitude", course.venue_latitude)
    longitude = changes.get("venue_longitude", course.venue_longitude)
    validate_coordinate_pair(latitude, longitude)
    for field, value in changes.items():
        setattr(course, field, value)
    append_audit_log(
        db,
        action="course_updated",
        request=request,
        user_id=current_user.id,
        resource_type="course",
        resource_id=course.id,
        details={"changed_fields": sorted(changes)},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Course code already exists") from None
    db.refresh(course)
    return course_response(course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    course.is_active = False
    append_audit_log(
        db,
        action="course_deleted",
        request=request,
        user_id=admin.id,
        resource_type="course",
        resource_id=course.id,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
