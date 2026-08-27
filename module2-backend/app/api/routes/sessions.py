from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_instructor
from app.core.database import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.session import AttendanceSession, SessionStatus
from app.models.user import User, UserRole
from app.schemas.session import PaginatedSessions, SessionCreate, SessionResponse, SessionUpdate
from app.services.audit import append_audit_log


router = APIRouter(prefix="/sessions", tags=["Sessions"])


def comparable_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def session_response(
    session: AttendanceSession,
    *,
    course_code: str | None = None,
    course_name: str | None = None,
    total_enrolled: int | None = None,
) -> SessionResponse:
    values = {
        column.name: getattr(session, column.name)
        for column in AttendanceSession.__table__.columns
        if column.name not in {"qr_code_secret", "qr_code_expires_at"}
    }
    return SessionResponse(
        **values,
        course_code=course_code,
        course_name=course_name,
        qr_code_enabled=session.qr_code_secret is not None,
        total_enrolled=total_enrolled,
        checked_in_count=0 if total_enrolled is not None else None,
    )


def session_row_query():
    total_enrolled = (
        select(func.count(Enrollment.id))
        .where(
            Enrollment.course_id == AttendanceSession.course_id,
            Enrollment.is_active.is_(True),
        )
        .correlate(AttendanceSession)
        .scalar_subquery()
    )
    return select(AttendanceSession, Course.code, Course.name, total_enrolled).join(
        Course, Course.id == AttendanceSession.course_id
    )


def validate_session_values(
    *,
    scheduled_start: datetime,
    scheduled_end: datetime,
    checkin_opens_at: datetime,
    checkin_closes_at: datetime,
    venue_latitude: float | None,
    venue_longitude: float | None,
    require_future_start: bool,
) -> None:
    if comparable_utc(scheduled_end) <= comparable_utc(scheduled_start):
        raise HTTPException(status_code=422, detail="Scheduled end must be after scheduled start")
    if require_future_start and comparable_utc(scheduled_start) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Scheduled start must be in the future")
    if comparable_utc(checkin_closes_at) <= comparable_utc(checkin_opens_at):
        raise HTTPException(status_code=422, detail="Check-in close must be after check-in open")
    if (venue_latitude is None) != (venue_longitude is None):
        raise HTTPException(
            status_code=422,
            detail="Venue latitude and longitude must be provided together",
        )


def validate_transition(current: SessionStatus, requested: SessionStatus) -> None:
    if current == requested:
        return
    allowed = {
        SessionStatus.scheduled: {SessionStatus.active, SessionStatus.cancelled},
        SessionStatus.active: {SessionStatus.closed, SessionStatus.cancelled},
        SessionStatus.closed: {SessionStatus.cancelled},
        SessionStatus.cancelled: set(),
    }
    if requested not in allowed[current]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid session status transition from {current.value} to {requested.value}",
        )


def apply_status(session: AttendanceSession, requested: SessionStatus) -> None:
    validate_transition(session.status, requested)
    if session.status == requested:
        return
    now = datetime.now(timezone.utc)
    if requested == SessionStatus.active:
        session.actual_start = now
    if requested in {SessionStatus.closed, SessionStatus.cancelled}:
        session.actual_end = now
    session.status = requested


@router.get("/", response_model=PaginatedSessions)
def list_sessions(
    session_status: SessionStatus | None = Query(default=None, alias="status"),
    course_id: str | None = None,
    instructor_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedSessions:
    if current_user.role not in {UserRole.instructor, UserRole.admin}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    filters = []
    if current_user.role == UserRole.instructor:
        filters.append(AttendanceSession.instructor_id == current_user.id)
        if instructor_id is not None and instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    elif instructor_id is not None:
        filters.append(AttendanceSession.instructor_id == instructor_id)
    if session_status is not None:
        filters.append(AttendanceSession.status == session_status)
    if course_id is not None:
        filters.append(AttendanceSession.course_id == course_id)
    if start_date is not None:
        filters.append(AttendanceSession.scheduled_start >= start_date)
    if end_date is not None:
        filters.append(AttendanceSession.scheduled_start <= end_date)

    total = db.scalar(select(func.count()).select_from(AttendanceSession).where(*filters)) or 0
    rows = db.execute(
        session_row_query()
        .where(*filters)
        .order_by(AttendanceSession.scheduled_start.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return PaginatedSessions(
        items=[
            session_response(
                session,
                course_code=course_code,
                course_name=course_name,
                total_enrolled=total_enrolled,
            )
            for session, course_code, course_name, total_enrolled in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/active", response_model=list[SessionResponse])
def active_sessions(db: Session = Depends(get_db)) -> list[SessionResponse]:
    now = datetime.now(timezone.utc)
    rows = db.execute(
        session_row_query()
        .where(
            AttendanceSession.status == SessionStatus.active,
            AttendanceSession.checkin_opens_at <= now,
            AttendanceSession.checkin_closes_at >= now,
            Course.is_active.is_(True),
        )
        .order_by(AttendanceSession.checkin_closes_at)
    ).all()
    return [
        session_response(
            session,
            course_code=course_code,
            course_name=course_name,
            total_enrolled=total_enrolled,
        )
        for session, course_code, course_name, total_enrolled in rows
    ]


@router.get("/my-sessions", response_model=list[SessionResponse])
def my_sessions(
    session_status: SessionStatus | None = Query(default=None, alias="status"),
    upcoming: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    query = session_row_query()
    if current_user.role == UserRole.student:
        query = query.join(
            Enrollment,
            (Enrollment.course_id == AttendanceSession.course_id)
            & (Enrollment.student_id == current_user.id)
            & Enrollment.is_active.is_(True),
        )
    elif current_user.role == UserRole.instructor:
        query = query.where(AttendanceSession.instructor_id == current_user.id)
    elif current_user.role == UserRole.ta:
        return []
    if session_status is not None:
        query = query.where(AttendanceSession.status == session_status)
    if upcoming:
        query = query.where(AttendanceSession.scheduled_start >= datetime.now(timezone.utc))
    rows = db.execute(query.order_by(AttendanceSession.scheduled_start).limit(limit)).all()
    return [
        session_response(
            session,
            course_code=course_code,
            course_name=course_name,
            total_enrolled=total_enrolled,
        )
        for session, course_code, course_name, total_enrolled in rows
    ]


@router.get("/{session_id}", response_model=SessionResponse)
def read_session(
    session_id: str,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    row = db.execute(session_row_query().where(AttendanceSession.id == session_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_response(row[0], course_code=row[1], course_name=row[2], total_enrolled=row[3])


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    request: Request,
    instructor: User = Depends(require_instructor),
    db: Session = Depends(get_db),
) -> SessionResponse:
    course = db.get(Course, payload.course_id)
    if course is None or not course.is_active:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id is not None and course.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if course.instructor_id is None:
        course.instructor_id = instructor.id

    checkin_opens_at = payload.checkin_opens_at or payload.scheduled_start - timedelta(minutes=15)
    checkin_closes_at = payload.checkin_closes_at or payload.scheduled_start + timedelta(minutes=30)
    venue_latitude = (
        payload.venue_latitude if payload.venue_latitude is not None else course.venue_latitude
    )
    venue_longitude = (
        payload.venue_longitude if payload.venue_longitude is not None else course.venue_longitude
    )
    validate_session_values(
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        checkin_opens_at=checkin_opens_at,
        checkin_closes_at=checkin_closes_at,
        venue_latitude=venue_latitude,
        venue_longitude=venue_longitude,
        require_future_start=True,
    )
    values = payload.model_dump(exclude={"checkin_opens_at", "checkin_closes_at"})
    values.update(
        instructor_id=instructor.id,
        checkin_opens_at=checkin_opens_at,
        checkin_closes_at=checkin_closes_at,
        venue_latitude=venue_latitude,
        venue_longitude=venue_longitude,
        venue_name=payload.venue_name or course.venue_name,
        geofence_radius_meters=payload.geofence_radius_meters or course.geofence_radius_meters,
        risk_threshold=payload.risk_threshold if payload.risk_threshold is not None else course.risk_threshold,
    )
    session = AttendanceSession(**values)
    db.add(session)
    db.flush()
    append_audit_log(
        db,
        action="session_created",
        request=request,
        user_id=instructor.id,
        resource_type="session",
        resource_id=session.id,
        details={"course_id": course.id},
    )
    db.commit()
    db.refresh(session)
    total_enrolled = db.scalar(
        select(func.count(Enrollment.id)).where(
            Enrollment.course_id == course.id, Enrollment.is_active.is_(True)
        )
    ) or 0
    return session_response(
        session,
        course_code=course.code,
        course_name=course.name,
        total_enrolled=total_enrolled,
    )


@router.patch("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    payload: SessionUpdate,
    request: Request,
    instructor: User = Depends(require_instructor),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = db.get(AttendanceSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    changes = payload.model_dump(exclude_unset=True)
    requested_status = changes.pop("status", None)
    scheduled_start = changes.get("scheduled_start", session.scheduled_start)
    scheduled_end = changes.get("scheduled_end", session.scheduled_end)
    checkin_opens_at = changes.get("checkin_opens_at", session.checkin_opens_at)
    checkin_closes_at = changes.get("checkin_closes_at", session.checkin_closes_at)
    venue_latitude = changes.get("venue_latitude", session.venue_latitude)
    venue_longitude = changes.get("venue_longitude", session.venue_longitude)
    validate_session_values(
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        checkin_opens_at=checkin_opens_at,
        checkin_closes_at=checkin_closes_at,
        venue_latitude=venue_latitude,
        venue_longitude=venue_longitude,
        require_future_start=session.status == SessionStatus.scheduled,
    )
    for field, value in changes.items():
        setattr(session, field, value)
    if requested_status is not None:
        apply_status(session, requested_status)
    changed_fields = sorted([*changes, *( ["status"] if requested_status is not None else [])])
    append_audit_log(
        db,
        action="session_updated",
        request=request,
        user_id=instructor.id,
        resource_type="session",
        resource_id=session.id,
        details={"changed_fields": changed_fields},
    )
    db.commit()
    db.refresh(session)
    course = db.get(Course, session.course_id)
    total_enrolled = db.scalar(
        select(func.count(Enrollment.id)).where(
            Enrollment.course_id == session.course_id, Enrollment.is_active.is_(True)
        )
    ) or 0
    return session_response(
        session,
        course_code=course.code if course else None,
        course_name=course.name if course else None,
        total_enrolled=total_enrolled,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    request: Request,
    instructor: User = Depends(require_instructor),
    db: Session = Depends(get_db),
) -> Response:
    session = db.get(AttendanceSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.instructor_id != instructor.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if session.status != SessionStatus.scheduled:
        raise HTTPException(status_code=400, detail="Only scheduled sessions can be deleted")
    session_id_value = session.id
    db.delete(session)
    append_audit_log(
        db,
        action="session_deleted",
        request=request,
        user_id=instructor.id,
        resource_type="session",
        resource_id=session_id_value,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
