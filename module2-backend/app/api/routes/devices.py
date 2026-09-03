import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.models.device import Device, DeviceTrustScore
from app.models.user import User, UserRole
from app.schemas.device import (
    DeviceRegister,
    DeviceResponse,
    DeviceUpdate,
    LegacyDeviceRegister,
    PaginatedDevices,
)
from app.services.audit import append_audit_log


router = APIRouter(prefix="/devices", tags=["Devices"])


def require_device_owner_or_admin(current_user: User, device: Device) -> None:
    if current_user.role != UserRole.admin and device.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def get_device_or_404(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def unattested_key(fingerprint: str) -> str:
    """Return a non-secret placeholder for legacy clients that do not send a key."""

    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return f"unattested:{digest}"


def create_device(
    payload: DeviceRegister | LegacyDeviceRegister,
    request: Request,
    current_user: User,
    db: Session,
) -> Device:
    existing = db.scalar(
        select(Device).where(Device.device_fingerprint == payload.device_fingerprint)
    )
    if existing is not None:
        if existing.user_id != current_user.id:
            append_audit_log(
                db,
                action="security_violation",
                request=request,
                user_id=current_user.id,
                resource_type="device",
                resource_id=existing.id,
                device_id=existing.id,
                details={"violation_type": "device_fingerprint_reuse"},
                success=False,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Device fingerprint is already bound to another account",
            )
        raise HTTPException(status_code=400, detail="Device is already registered")

    device = Device(
        user_id=current_user.id,
        device_fingerprint=payload.device_fingerprint,
        device_name=payload.device_name,
        platform=payload.platform,
        browser=payload.browser,
        os_version=payload.os_version,
        app_version=payload.app_version,
        public_key=payload.public_key or unattested_key(payload.device_fingerprint),
    )
    db.add(device)
    try:
        db.flush()
        append_audit_log(
            db,
            action="device_registered",
            request=request,
            user_id=current_user.id,
            resource_type="device",
            resource_id=device.id,
            device_id=device.id,
            details={
                "platform": device.platform.value if device.platform else None,
                "public_key_supplied": payload.public_key is not None,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Device fingerprint is already registered"
        ) from None
    db.refresh(device)
    return device


@router.post(
    "/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED
)
def register_device(
    payload: DeviceRegister,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Device:
    return create_device(payload, request, current_user, db)


@router.post(
    "/",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def register_legacy_device(
    payload: LegacyDeviceRegister,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Device:
    return create_device(payload, request, current_user, db)


@router.get("/my-devices", response_model=list[DeviceResponse])
def list_my_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Device]:
    return list(
        db.scalars(
            select(Device)
            .where(Device.user_id == current_user.id)
            .order_by(Device.last_seen_at.desc())
        ).all()
    )


@router.get("/", response_model=PaginatedDevices)
def list_devices(
    is_active: bool | None = None,
    is_trusted: bool | None = None,
    user_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedDevices:
    filters = []
    if is_active is not None:
        filters.append(Device.is_active == is_active)
    if is_trusted is not None:
        filters.append(Device.is_trusted == is_trusted)
    if user_id is not None:
        filters.append(Device.user_id == user_id)

    total = db.scalar(select(func.count()).select_from(Device).where(*filters)) or 0
    devices = db.scalars(
        select(Device)
        .where(*filters)
        .order_by(Device.last_seen_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return PaginatedDevices(
        items=[DeviceResponse.model_validate(device) for device in devices],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{device_id}", response_model=DeviceResponse)
def read_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Device:
    device = get_device_or_404(db, device_id)
    require_device_owner_or_admin(current_user, device)
    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: str,
    payload: DeviceUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Device:
    device = get_device_or_404(db, device_id)
    require_device_owner_or_admin(current_user, device)
    changes = payload.model_dump(exclude_unset=True)
    if "is_trusted" in changes and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=403, detail="Only admins can change device trust"
        )
    if (
        changes.get("is_active") is True
        and not device.is_active
        and current_user.role != UserRole.admin
    ):
        raise HTTPException(
            status_code=403, detail="Only admins can reactivate a revoked device"
        )

    if "device_name" in changes:
        device.device_name = changes["device_name"]
    if "is_trusted" in changes:
        device.is_trusted = changes["is_trusted"]
        device.trust_score = (
            DeviceTrustScore.high if device.is_trusted else DeviceTrustScore.low
        )
    if "is_active" in changes:
        device.is_active = changes["is_active"]
        if device.is_active:
            device.revoked_at = None
            device.revocation_reason = None
        else:
            device.revoked_at = datetime.now(timezone.utc)
            device.revocation_reason = (
                "deactivated_by_admin"
                if current_user.role == UserRole.admin
                else "deactivated_by_owner"
            )

    append_audit_log(
        db,
        action="device_updated",
        request=request,
        user_id=current_user.id,
        resource_type="device",
        resource_id=device.id,
        device_id=device.id,
        details={"changed_fields": sorted(changes)},
    )
    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device(
    device_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    device = get_device_or_404(db, device_id)
    require_device_owner_or_admin(current_user, device)
    device.is_active = False
    device.revoked_at = datetime.now(timezone.utc)
    device.revocation_reason = (
        "revoked_by_admin"
        if current_user.role == UserRole.admin
        else "revoked_by_owner"
    )
    append_audit_log(
        db,
        action="device_revoked",
        request=request,
        user_id=current_user.id,
        resource_type="device",
        resource_id=device.id,
        device_id=device.id,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
