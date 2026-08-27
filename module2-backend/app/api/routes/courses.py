from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.models.course import Course
from app.models.user import User, UserRole
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate, PaginatedCourses
from app.services.audit import append_audit_log


router = APIRouter(prefix="/courses", tags=["Courses"])


def course_response(course: Course, instructor_name: str | None = None) -> CourseResponse:
    values = {column.name: getattr(course, column.name) for column in Course.__table__.columns}
    return CourseResponse(**values, instructor_name=instructor_name)


def validate_instructor(db: Session, instructor_id: str | None) -> None:
    if instructor_id is None:
        return
    instructor = db.get(User, instructor_id)
    if instructor is None or instructor.role != UserRole.instructor or not instructor.is_active:
        raise HTTPException(status_code=400, detail="Instructor must be an active instructor user")


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
    instructor_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedCourses:
    filters = []
    if is_active is not None:
        filters.append(Course.is_active == is_active)
    if semester is not None:
        filters.append(Course.semester == semester)
    if instructor_id is not None:
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        filters.append(Course.instructor_id == instructor_id)
    elif current_user.role == UserRole.instructor:
        filters.append(or_(Course.instructor_id == current_user.id, Course.instructor_id.is_(None)))

    total = db.scalar(select(func.count()).select_from(Course).where(*filters)) or 0
    rows = db.execute(
        select(Course, User.full_name)
        .outerjoin(User, User.id == Course.instructor_id)
        .where(*filters)
        .order_by(Course.code)
        .limit(limit)
        .offset(offset)
    ).all()
    return PaginatedCourses(
        items=[course_response(course, instructor_name) for course, instructor_name in rows],
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
    row = db.execute(
        select(Course, User.full_name)
        .outerjoin(User, User.id == Course.instructor_id)
        .where(Course.id == course_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course_response(row[0], row[1])


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CourseResponse:
    validate_instructor(db, payload.instructor_id)
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
    instructor_name = (
        db.scalar(select(User.full_name).where(User.id == course.instructor_id))
        if course.instructor_id
        else None
    )
    return course_response(course, instructor_name)


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
    if current_user.role != UserRole.admin and not (
        current_user.role == UserRole.instructor and course.instructor_id == current_user.id
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    changes = payload.model_dump(exclude_unset=True)
    if current_user.role != UserRole.admin and ({"instructor_id", "is_active"} & changes.keys()):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if "instructor_id" in changes:
        validate_instructor(db, changes["instructor_id"])
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
    instructor_name = (
        db.scalar(select(User.full_name).where(User.id == course.instructor_id))
        if course.instructor_id
        else None
    )
    return course_response(course, instructor_name)


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
