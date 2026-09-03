from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import (
    AUTHENTICATED_API_RATE_LIMIT,
    RateLimiter,
    check_rate_limit,
    get_rate_limiter,
)
from app.core.security import TokenValidationError, decode_token
from app.models.user import User, UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenValidationError:
        raise unauthorized from None

    user = db.get(User, payload["sub"])
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    check_rate_limit(
        limiter=limiter,
        policy=AUTHENTICATED_API_RATE_LIMIT,
        identifier=user.id,
    )
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    allowed = set(roles)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


require_admin = require_roles(UserRole.admin)
require_instructor = require_roles(UserRole.instructor)
require_instructor_or_admin = require_roles(UserRole.instructor, UserRole.admin)
