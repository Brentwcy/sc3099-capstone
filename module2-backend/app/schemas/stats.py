from datetime import datetime

from pydantic import BaseModel

from app.models.session import SessionStatus


class TimelineBucket(BaseModel):
    minute: int
    count: int


class RiskDistribution(BaseModel):
    low: int
    medium: int
    high: int


class SessionAttendanceSummary(BaseModel):
    session_id: str
    session_name: str
    course_code: str
    scheduled_start: datetime
    status: SessionStatus
    total_enrolled: int
    checked_in: int
    attendance_rate: float
    by_status: dict[str, int]
    average_risk_score: float
    average_distance_meters: float | None
    average_checkin_time_minutes: float | None
    risk_distribution: RiskDistribution
    checkin_timeline: list[TimelineBucket]
