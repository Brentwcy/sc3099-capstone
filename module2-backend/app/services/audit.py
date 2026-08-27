import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def request_metadata(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent[:500] if user_agent else None


def append_audit_log(
    db: Session,
    *,
    action: str,
    request: Request,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    success: bool = True,
) -> AuditLog:
    """Add an audit event to the caller's current transaction."""

    ip_address, user_agent = request_metadata(request)
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=json.dumps(details, separators=(",", ":"), sort_keys=True) if details else None,
        success=success,
    )
    db.add(log)
    return log
