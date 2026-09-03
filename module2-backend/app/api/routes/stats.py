from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.checkin import CheckIn, CheckInStatus
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.session import AttendanceSession
from app.models.user import User, UserRole
from app.schemas.stats import RiskDistribution, SessionAttendanceSummary, TimelineBucket


router = APIRouter(prefix="/stats", tags=["Statistics"])


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def require_summary_access(
    current_user: User, attendance_session: AttendanceSession
) -> None:
    if current_user.role in {UserRole.admin, UserRole.ta}:
        return
    if (
        current_user.role == UserRole.instructor
        and attendance_session.instructor_id == current_user.id
    ):
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/sessions/{session_id}", response_model=SessionAttendanceSummary)
def session_attendance_summary(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionAttendanceSummary:
    row = db.execute(
        select(AttendanceSession, Course.code)
        .join(Course, Course.id == AttendanceSession.course_id)
        .where(AttendanceSession.id == session_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    attendance_session, course_code = row
    require_summary_access(current_user, attendance_session)

    total_enrolled = (
        db.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(
                Enrollment.course_id == attendance_session.course_id,
                Enrollment.is_active.is_(True),
            )
        )
        or 0
    )
    checkins = list(
        db.scalars(
            select(CheckIn)
            .where(CheckIn.session_id == attendance_session.id)
            .order_by(CheckIn.checked_in_at)
        ).all()
    )
    checked_in = len(checkins)
    status_counts = Counter(checkin.status.value for checkin in checkins)
    by_status = {item.value: status_counts[item.value] for item in CheckInStatus}

    risk_scores = [checkin.risk_score for checkin in checkins]
    distances = [
        checkin.distance_from_venue_meters
        for checkin in checkins
        if checkin.distance_from_venue_meters is not None
    ]
    scheduled_start = as_utc(attendance_session.scheduled_start)
    minute_counts = Counter(
        max(
            0,
            int(
                (as_utc(checkin.checked_in_at) - scheduled_start).total_seconds() // 60
            ),
        )
        for checkin in checkins
    )
    checkin_minutes = [
        max(0.0, (as_utc(checkin.checked_in_at) - scheduled_start).total_seconds() / 60)
        for checkin in checkins
    ]

    return SessionAttendanceSummary(
        session_id=attendance_session.id,
        session_name=attendance_session.name,
        course_code=course_code,
        scheduled_start=attendance_session.scheduled_start,
        status=attendance_session.status,
        total_enrolled=total_enrolled,
        checked_in=checked_in,
        attendance_rate=(
            round(checked_in / total_enrolled, 4) if total_enrolled else 0.0
        ),
        by_status=by_status,
        average_risk_score=(
            round(sum(risk_scores) / checked_in, 4) if checked_in else 0.0
        ),
        average_distance_meters=(
            round(sum(distances) / len(distances), 2) if distances else None
        ),
        average_checkin_time_minutes=(
            round(sum(checkin_minutes) / len(checkin_minutes), 2)
            if checkin_minutes
            else None
        ),
        risk_distribution=RiskDistribution(
            low=sum(score < 0.3 for score in risk_scores),
            medium=sum(0.3 <= score < 0.5 for score in risk_scores),
            high=sum(score >= 0.5 for score in risk_scores),
        ),
        checkin_timeline=[
            TimelineBucket(minute=minute, count=count)
            for minute, count in sorted(minute_counts.items())
        ],
    )
