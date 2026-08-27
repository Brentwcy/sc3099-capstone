import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogResponse, PaginatedAuditLogs


router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/", response_model=PaginatedAuditLogs)
def list_audit_logs(
    user_id: str | None = None,
    action: str | None = Query(default=None, max_length=50),
    resource_type: str | None = Query(default=None, max_length=50),
    resource_id: str | None = None,
    success: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedAuditLogs:
    filters = []
    for column, value in (
        (AuditLog.user_id, user_id),
        (AuditLog.action, action),
        (AuditLog.resource_type, resource_type),
        (AuditLog.resource_id, resource_id),
        (AuditLog.success, success),
    ):
        if value is not None:
            filters.append(column == value)
    if start_date is not None:
        filters.append(AuditLog.timestamp >= start_date)
    if end_date is not None:
        filters.append(AuditLog.timestamp <= end_date)

    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    rows = db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(*filters)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_email=email,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            device_id=log.device_id,
            details=json.loads(log.details) if log.details else None,
            success=log.success,
            timestamp=log.timestamp,
        )
        for log, email in rows
    ]
    return PaginatedAuditLogs(items=items, total=total, limit=limit, offset=offset)
