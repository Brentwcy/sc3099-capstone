from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.rate_limit import enforce_login_rate_limit, enforce_registration_rate_limit
from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, LogoutResponse, RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserResponse
from app.services.audit import append_audit_log


router = APIRouter(prefix="/auth", tags=["Authentication"])


def token_pair_for(user: User) -> TokenPair:
    role = user.role.value
    return TokenPair(
        access_token=create_access_token(subject=user.id, email=user.email, role=role),
        refresh_token=create_refresh_token(subject=user.id, email=user.email, role=role),
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_registration_rate_limit)],
)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    user = User(
        email=str(payload.email),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.flush()
        append_audit_log(
            db,
            action="user_created",
            request=request,
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered") from None
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(enforce_login_rate_limit)],
)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        append_audit_log(
            db,
            action="login_failed",
            request=request,
            user_id=user.id if user else None,
            resource_type="user",
            resource_id=user.id if user else None,
            details={"email": email, "reason": "invalid_credentials"},
            success=False,
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        append_audit_log(
            db,
            action="login_failed",
            request=request,
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            details={"email": email, "reason": "account_disabled"},
            success=False,
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login_at = datetime.now(timezone.utc)
    append_audit_log(
        db,
        action="login_success",
        request=request,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
    )
    db.commit()
    db.refresh(user)
    tokens = token_pair_for(user)
    return LoginResponse(**tokens.model_dump(), user=UserResponse.model_validate(user))


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    unauthorized = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenValidationError:
        raise unauthorized from None
    user = db.get(User, token_payload["sub"])
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return token_pair_for(user)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    append_audit_log(
        db,
        action="logout",
        request=request,
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
    )
    db.commit()
    return LogoutResponse(message="Logged out successfully")
