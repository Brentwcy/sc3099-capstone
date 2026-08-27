from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.schemas.enrollment import (
    BulkEnrollmentDetail,
    BulkEnrollmentRequest,
    BulkEnrollmentResponse,
    CourseEnrollmentsResponse,
    EnrolledStudentResponse,
    EnrollmentCreate,
    EnrollmentResponse,
    MyEnrollmentResponse,
)
from app.services.audit import append_audit_log
from app.services.enrollment import create_or_reactivate_enrollment


router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


def require_course_manager(
    user: User,
    course: Course,
    *,
    claim_unassigned: bool = False,
    allow_ta_read: bool = False,
) -> None:
    if user.role == UserRole.admin:
        return
    if allow_ta_read and user.role == UserRole.ta:
        return
    if user.role != UserRole.instructor:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if course.instructor_id is not None and course.instructor_id != user.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if claim_unassigned and course.instructor_id is None:
        course.instructor_id = user.id


def enrollment_response(enrollment: Enrollment) -> EnrollmentResponse:
    return EnrollmentResponse(
        id=enrollment.id,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
        is_active=enrollment.is_active,
        enrolled_at=enrollment.enrolled_at,
        dropped_at=enrollment.dropped_at,
    )


@router.get("/my-enrollments", response_model=list[MyEnrollmentResponse])
def my_enrollments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MyEnrollmentResponse]:
    if current_user.role != UserRole.student:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    instructor = User.__table__.alias("instructor")
    rows = db.execute(
        select(Enrollment, Course, instructor.c.full_name)
        .join(Course, Course.id == Enrollment.course_id)
        .outerjoin(instructor, instructor.c.id == Course.instructor_id)
        .where(Enrollment.student_id == current_user.id, Enrollment.is_active.is_(True))
        .order_by(Course.code)
    ).all()
    return [
        MyEnrollmentResponse(
            **enrollment_response(enrollment).model_dump(),
            course_code=course.code,
            course_name=course.name,
            semester=course.semester,
            instructor_name=instructor_name,
        )
        for enrollment, course, instructor_name in rows
    ]


@router.get("/course/{course_id}", response_model=CourseEnrollmentsResponse)
def course_enrollments(
    course_id: str,
    is_active: bool | None = True,
    search: str | None = Query(default=None, max_length=255),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseEnrollmentsResponse:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    require_course_manager(current_user, course, allow_ta_read=True)

    filters = [Enrollment.course_id == course.id]
    if is_active is not None:
        filters.append(Enrollment.is_active == is_active)
    if search:
        needle = f"%{search.strip().lower()}%"
        filters.append(
            or_(func.lower(User.email).like(needle), func.lower(User.full_name).like(needle))
        )
    rows = db.execute(
        select(Enrollment, User)
        .join(User, User.id == Enrollment.student_id)
        .where(*filters)
        .order_by(User.full_name, User.email)
    ).all()
    students = [
        EnrolledStudentResponse(
            id=enrollment.id,
            student_id=student.id,
            student_email=student.email,
            student_name=student.full_name,
            enrolled_at=enrollment.enrolled_at,
            is_active=enrollment.is_active,
            face_enrolled=student.face_enrolled,
        )
        for enrollment, student in rows
    ]
    return CourseEnrollmentsResponse(
        course_id=course.id,
        course_code=course.code,
        total_enrolled=len(students),
        students=students,
    )


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def create_enrollment(
    payload: EnrollmentCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnrollmentResponse:
    course = db.get(Course, payload.course_id)
    if course is None or not course.is_active:
        raise HTTPException(status_code=404, detail="Course not found")
    require_course_manager(current_user, course, claim_unassigned=True)
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
        user_id=current_user.id,
        resource_type="enrollment",
        resource_id=enrollment.id,
        details={"course_id": course.id, "student_id": enrollment.student_id},
    )
    db.commit()
    db.refresh(enrollment)
    return enrollment_response(enrollment)


@router.post("/bulk", response_model=BulkEnrollmentResponse)
def bulk_enrollments(
    payload: BulkEnrollmentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BulkEnrollmentResponse:
    course = db.get(Course, payload.course_id)
    if course is None or not course.is_active:
        raise HTTPException(status_code=404, detail="Course not found")
    require_course_manager(current_user, course, claim_unassigned=True)
    if payload.create_accounts:
        raise HTTPException(
            status_code=400,
            detail="Account creation requires the admin user setup endpoint",
        )

    enrolled = already_enrolled = not_found = 0
    details: list[BulkEnrollmentDetail] = []
    for email_value in payload.student_emails:
        email = str(email_value)
        student = db.scalar(
            select(User).where(User.email == email, User.role == UserRole.student)
        )
        if student is None:
            not_found += 1
            details.append(BulkEnrollmentDetail(email=email, status="not_found"))
            continue
        existing = db.scalar(
            select(Enrollment).where(
                Enrollment.student_id == student.id,
                Enrollment.course_id == course.id,
            )
        )
        if existing is not None and existing.is_active:
            already_enrolled += 1
            details.append(BulkEnrollmentDetail(email=email, status="already_enrolled"))
            continue
        enrollment = create_or_reactivate_enrollment(
            db,
            student_id=student.id,
            course_id=course.id,
        )
        db.flush()
        append_audit_log(
            db,
            action="enrollment_created",
            request=request,
            user_id=current_user.id,
            resource_type="enrollment",
            resource_id=enrollment.id,
            details={"course_id": course.id, "student_id": student.id, "bulk": True},
        )
        enrolled += 1
        details.append(BulkEnrollmentDetail(email=email, status="enrolled"))
    db.commit()
    return BulkEnrollmentResponse(
        enrolled=enrolled,
        already_enrolled=already_enrolled,
        not_found=not_found,
        created=0,
        details=details,
    )


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment(
    enrollment_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    course = db.get(Course, enrollment.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    require_course_manager(current_user, course)
    enrollment.is_active = False
    enrollment.dropped_at = datetime.now(timezone.utc)
    append_audit_log(
        db,
        action="enrollment_deleted",
        request=request,
        user_id=current_user.id,
        resource_type="enrollment",
        resource_id=enrollment.id,
        details={"course_id": course.id, "student_id": enrollment.student_id},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
