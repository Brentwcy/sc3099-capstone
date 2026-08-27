import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.models.checkin import CheckIn, CheckInStatus
from app.models.course import Course
from app.models.device import Device
from app.models.enrollment import Enrollment
from app.models.risk_signal import RiskSeverity, RiskSignal, RiskSignalType
from app.models.session import AttendanceSession, SessionStatus
from app.models.user import User, UserRole
from app.schemas.checkin import (
    CheckInCreate,
    CheckInDetailResponse,
    CheckInResponse,
    MyCheckInResponse,
    RiskFactorResponse,
    SessionCheckInResponse,
)
from app.services.checkin import (
    InitialRiskFactor,
    haversine_distance_meters,
    initial_risk_score,
)
from app.services.face_mock import FaceService, get_face_service


router = APIRouter(prefix="/checkins", tags=["Check-ins"])


def comparable_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_risk_factors(value: str | None) -> list[RiskFactorResponse]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [RiskFactorResponse.model_validate(item) for item in parsed]


def checkin_response(
    checkin: CheckIn,
    *,
    device_trusted: bool | None = None,
) -> CheckInResponse:
    return CheckInResponse(
        id=checkin.id,
        session_id=checkin.session_id,
        student_id=checkin.student_id,
        status=checkin.status,
        checked_in_at=checkin.checked_in_at,
        latitude=checkin.latitude,
        longitude=checkin.longitude,
        location_accuracy_meters=checkin.location_accuracy_meters,
        distance_from_venue_meters=checkin.distance_from_venue_meters,
        liveness_passed=checkin.liveness_passed,
        liveness_score=checkin.liveness_score,
        face_match_passed=checkin.face_match_passed,
        face_match_score=checkin.face_match_score,
        risk_score=checkin.risk_score,
        risk_factors=parse_risk_factors(checkin.risk_factors),
    )


def checkin_detail_response(
    checkin: CheckIn,
    *,
    device_trusted: bool | None,
) -> CheckInDetailResponse:
    base = checkin_response(checkin).model_dump()
    return CheckInDetailResponse(
        **base,
        device_id=checkin.device_id,
        device_trusted=device_trusted,
        verified_at=checkin.verified_at,
        reviewed_by_id=checkin.reviewed_by_id,
        reviewed_at=checkin.reviewed_at,
        review_notes=checkin.review_notes,
        appeal_reason=checkin.appeal_reason,
        appealed_at=checkin.appealed_at,
    )


def require_session_reader(current_user: User, session: AttendanceSession) -> None:
    if current_user.role in {UserRole.admin, UserRole.ta}:
        return
    if (
        current_user.role == UserRole.instructor
        and session.instructor_id == current_user.id
    ):
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.post("/", response_model=CheckInResponse, status_code=status.HTTP_201_CREATED)
async def create_checkin(
    payload: CheckInCreate,
    student: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
) -> CheckInResponse:
    attendance_session = db.get(AttendanceSession, payload.session_id)
    if attendance_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.course_id == attendance_session.course_id,
            Enrollment.is_active.is_(True),
        )
    )
    if enrollment is None:
        raise HTTPException(status_code=400, detail="Student is not enrolled in this course")
    if attendance_session.status != SessionStatus.active:
        raise HTTPException(status_code=400, detail="Session is not active")

    now = datetime.now(timezone.utc)
    if not (
        comparable_utc(attendance_session.checkin_opens_at)
        <= now
        <= comparable_utc(attendance_session.checkin_closes_at)
    ):
        raise HTTPException(status_code=400, detail="Check-in window is closed")
    if not student.camera_consent or not student.geolocation_consent:
        raise HTTPException(
            status_code=400,
            detail="Camera and geolocation consent are required",
        )

    existing = db.scalar(
        select(CheckIn).where(
            CheckIn.session_id == attendance_session.id,
            CheckIn.student_id == student.id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=400, detail="Already checked in")

    course = db.get(Course, attendance_session.course_id)
    if course is None or not course.is_active:
        raise HTTPException(status_code=400, detail="Course is not active")

    device = db.scalar(
        select(Device).where(
            Device.device_fingerprint == payload.device_fingerprint,
            Device.user_id == student.id,
            Device.is_active.is_(True),
        )
    )
    factors: list[InitialRiskFactor] = []
    if device is None:
        factors.append(
            InitialRiskFactor(
                RiskSignalType.device_unknown,
                RiskSeverity.medium,
                0.15,
            )
        )
    else:
        if not device.is_trusted:
            factors.append(
                InitialRiskFactor(
                    RiskSignalType.attestation_failed,
                    RiskSeverity.medium,
                    0.20,
                )
            )
        if device.is_emulator:
            factors.append(
                InitialRiskFactor(
                    RiskSignalType.device_emulator,
                    RiskSeverity.high,
                    0.20,
                )
            )
        if device.is_rooted_jailbroken:
            factors.append(
                InitialRiskFactor(
                    RiskSignalType.device_rooted,
                    RiskSeverity.high,
                    0.20,
                )
            )

    venue_latitude = attendance_session.venue_latitude
    venue_longitude = attendance_session.venue_longitude
    geofence_radius = attendance_session.geofence_radius_meters
    distance: float | None = None
    outside_geofence = False
    far_outside_geofence = False
    if (
        venue_latitude is not None
        and venue_longitude is not None
        and geofence_radius is not None
    ):
        distance = haversine_distance_meters(
            payload.latitude,
            payload.longitude,
            venue_latitude,
            venue_longitude,
        )
        outside_geofence = distance > geofence_radius
        far_outside_geofence = distance > geofence_radius * 2
        if outside_geofence:
            factors.append(
                InitialRiskFactor(
                    RiskSignalType.geo_out_of_bounds,
                    RiskSeverity.critical
                    if far_outside_geofence
                    else RiskSeverity.high,
                    0.40,
                    details={
                        "distance_meters": round(distance, 2),
                        "geofence_radius_meters": geofence_radius,
                    },
                )
            )
        if (
            payload.location_accuracy_meters is not None
            and payload.location_accuracy_meters > geofence_radius
        ):
            factors.append(
                InitialRiskFactor(
                    RiskSignalType.geo_accuracy_low,
                    RiskSeverity.medium,
                    0.10,
                    details={
                        "accuracy_meters": payload.location_accuracy_meters,
                    },
                )
            )

    if now > comparable_utc(attendance_session.scheduled_start):
        factors.append(
            InitialRiskFactor(
                RiskSignalType.unusual_time,
                RiskSeverity.low,
                0.10,
                details={"reason": "late_checkin"},
            )
        )

    liveness_result = None
    if payload.liveness_challenge_response is not None:
        liveness_result = await face_service.check_liveness(
            challenge_response=payload.liveness_challenge_response,
            challenge_type="passive",
        )
        if liveness_result.liveness_passed is False:
            factors.append(
                InitialRiskFactor(
                    RiskSignalType.liveness_failed,
                    RiskSeverity.critical,
                    0.25,
                    confidence=1.0 - liveness_result.liveness_score,
                )
            )
        elif liveness_result.liveness_score < liveness_result.liveness_threshold:
            factors.append(
                InitialRiskFactor(
                    RiskSignalType.liveness_low_confidence,
                    RiskSeverity.high,
                    0.25,
                    confidence=1.0 - liveness_result.liveness_score,
                )
            )
    elif attendance_session.require_liveness_check:
        factors.append(
            InitialRiskFactor(
                RiskSignalType.liveness_low_confidence,
                RiskSeverity.medium,
                0.25,
                details={"reason": "challenge_not_provided"},
            )
        )

    risk_threshold = (
        attendance_session.risk_threshold
        if attendance_session.risk_threshold is not None
        else course.risk_threshold
    )
    risk_score = initial_risk_score(factors)
    if outside_geofence and not far_outside_geofence:
        risk_score = max(risk_score, risk_threshold)
    liveness_failed = bool(
        liveness_result is not None and liveness_result.liveness_passed is False
    )
    if far_outside_geofence or liveness_failed:
        result_status = CheckInStatus.rejected
    elif risk_score >= risk_threshold:
        result_status = CheckInStatus.flagged
    else:
        result_status = CheckInStatus.approved

    public_factors = [factor.public_dict() for factor in factors]
    checkin = CheckIn(
        session_id=attendance_session.id,
        student_id=student.id,
        device_id=device.id if device is not None else None,
        status=result_status,
        checked_in_at=now,
        verified_at=now if result_status == CheckInStatus.approved else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_accuracy_meters=payload.location_accuracy_meters,
        distance_from_venue_meters=distance,
        liveness_passed=liveness_result.liveness_passed if liveness_result else None,
        liveness_score=liveness_result.liveness_score if liveness_result else None,
        liveness_challenge_type=liveness_result.challenge_type if liveness_result else None,
        face_embedding_hash=(
            liveness_result.face_embedding_hash if liveness_result else None
        ),
        risk_score=risk_score,
        risk_factors=json.dumps(public_factors, separators=(",", ":")),
        qr_code_verified=(
            attendance_session.qr_code_secret is not None
            and payload.qr_code == attendance_session.qr_code_secret
        ),
        scheduled_deletion_at=now + timedelta(days=30),
    )
    db.add(checkin)
    try:
        db.flush()
        for factor in factors:
            db.add(
                RiskSignal(
                    checkin_id=checkin.id,
                    signal_type=factor.signal_type,
                    severity=factor.severity,
                    confidence=factor.confidence,
                    details=(
                        json.dumps(factor.details, separators=(",", ":"))
                        if factor.details is not None
                        else None
                    ),
                    weight=factor.weight,
                    detected_at=now,
                )
            )
        if device is not None:
            device.last_seen_at = now
            device.total_checkins += 1
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Already checked in") from None
    db.refresh(checkin)
    return checkin_response(
        checkin,
        device_trusted=device.is_trusted if device is not None else None,
    )


@router.get("/my-checkins", response_model=list[MyCheckInResponse])
def list_my_checkins(
    course_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    student: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> list[MyCheckInResponse]:
    query = (
        select(CheckIn, AttendanceSession.name, Course.code)
        .join(AttendanceSession, AttendanceSession.id == CheckIn.session_id)
        .join(Course, Course.id == AttendanceSession.course_id)
        .where(CheckIn.student_id == student.id)
    )
    if course_id is not None:
        query = query.where(Course.id == course_id)

    rows = db.execute(query.order_by(CheckIn.checked_in_at.desc()).limit(limit)).all()
    return [
        MyCheckInResponse(
            id=checkin.id,
            session_id=checkin.session_id,
            session_name=session_name,
            course_code=course_code,
            status=checkin.status,
            checked_in_at=checkin.checked_in_at,
            risk_score=checkin.risk_score,
        )
        for checkin, session_name, course_code in rows
    ]


@router.get(
    "/session/{session_id}",
    response_model=list[SessionCheckInResponse],
)
def list_session_checkins(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionCheckInResponse]:
    attendance_session = db.get(AttendanceSession, session_id)
    if attendance_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    require_session_reader(current_user, attendance_session)
    rows = db.execute(
        select(CheckIn, User, Device.is_trusted)
        .join(User, User.id == CheckIn.student_id)
        .outerjoin(Device, Device.id == CheckIn.device_id)
        .where(CheckIn.session_id == session_id)
        .order_by(CheckIn.checked_in_at)
    ).all()
    return [
        SessionCheckInResponse(
            id=checkin.id,
            student_id=checkin.student_id,
            student_name=student.full_name,
            student_email=student.email,
            status=checkin.status,
            checked_in_at=checkin.checked_in_at,
            distance_from_venue_meters=checkin.distance_from_venue_meters,
            risk_score=checkin.risk_score,
            risk_factors=parse_risk_factors(checkin.risk_factors),
            liveness_passed=checkin.liveness_passed,
            device_trusted=device_trusted,
        )
        for checkin, student, device_trusted in rows
    ]


@router.get("/{checkin_id}", response_model=CheckInDetailResponse)
def read_checkin(
    checkin_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckInDetailResponse:
    row = db.execute(
        select(CheckIn, Device.is_trusted)
        .outerjoin(Device, Device.id == CheckIn.device_id)
        .where(CheckIn.id == checkin_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Check-in not found")
    checkin, device_trusted = row
    if current_user.role == UserRole.student:
        if checkin.student_id != current_user.id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    else:
        attendance_session = db.get(AttendanceSession, checkin.session_id)
        if attendance_session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        require_session_reader(current_user, attendance_session)
    return checkin_detail_response(
        checkin,
        device_trusted=device_trusted,
    )
