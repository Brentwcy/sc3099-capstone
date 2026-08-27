from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole


def get_enrollment_entities(
    db: Session,
    *,
    student_id: str,
    course_id: str,
) -> tuple[User, Course]:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student:
        raise HTTPException(status_code=404, detail="Student not found")
    course = db.get(Course, course_id)
    if course is None or not course.is_active:
        raise HTTPException(status_code=404, detail="Course not found")
    return student, course


def create_or_reactivate_enrollment(
    db: Session,
    *,
    student_id: str,
    course_id: str,
) -> Enrollment:
    get_enrollment_entities(db, student_id=student_id, course_id=course_id)
    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
        )
    )
    if enrollment is not None and enrollment.is_active:
        raise HTTPException(status_code=400, detail="Student already enrolled")
    if enrollment is not None:
        enrollment.is_active = True
        enrollment.enrolled_at = datetime.now(timezone.utc)
        enrollment.dropped_at = None
        return enrollment

    enrollment = Enrollment(student_id=student_id, course_id=course_id)
    db.add(enrollment)
    return enrollment
