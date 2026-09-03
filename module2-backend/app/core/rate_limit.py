from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from typing import Callable, Protocol

from fastapi import Depends, HTTPException, Request, status
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


@dataclass(frozen=True)
class RateLimitPolicy:
    name: str
    limit: int
    window_seconds: int


AUTHENTICATED_API_RATE_LIMIT = RateLimitPolicy(name="api", limit=1_000, window_seconds=60 * 60)


def get_registration_rate_limit() -> RateLimitPolicy:
    """Use the configured limit; Settings preserves the 10/hour production default."""
    return RateLimitPolicy(
        name="registration",
        limit=get_settings().registration_rate_limit_per_hour,
        window_seconds=60 * 60,
    )


def get_login_rate_limit() -> RateLimitPolicy:
    """Use the configured limit; Settings preserves the 60/hour production default."""
    return RateLimitPolicy(
        name="login",
        limit=get_settings().login_rate_limit_per_hour,
        window_seconds=60 * 60,
    )


class RateLimiter(Protocol):
    def consume(self, *, policy: RateLimitPolicy, identifier: str) -> int | None:
        """Consume one attempt and return retry-after seconds when it is rejected."""


_FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if current == 1 or ttl < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
    ttl = tonumber(ARGV[1])
end
if current > tonumber(ARGV[2]) then
    return ttl
end
return -1
"""


class RedisRateLimiter:
    """Atomic, fixed-window limiter backed by the shared Redis service."""

    def __init__(self, client: Redis) -> None:
        self.client = client

    def consume(self, *, policy: RateLimitPolicy, identifier: str) -> int | None:
        identifier_hash = sha256(identifier.encode("utf-8")).hexdigest()
        key = f"saiv:rate-limit:{policy.name}:{identifier_hash}"
        retry_after = self.client.eval(
            _FIXED_WINDOW_SCRIPT,
            1,
            key,
            policy.window_seconds,
            policy.limit,
        )
        retry_after_seconds = int(retry_after)
        return retry_after_seconds if retry_after_seconds >= 0 else None


@lru_cache
def get_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


@lru_cache
def get_rate_limiter() -> RedisRateLimiter:
    return RedisRateLimiter(get_redis_client())


def client_identifier(request: Request) -> str:
    # Do not trust a caller-supplied forwarding header. Uvicorn may normalize a
    # trusted proxy address into request.client before this code runs.
    return request.client.host if request.client else "unknown"


def check_rate_limit(
    *,
    limiter: RateLimiter,
    policy: RateLimitPolicy,
    identifier: str,
) -> None:
    try:
        retry_after = limiter.consume(policy=policy, identifier=identifier)
    except RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service unavailable",
        ) from None

    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(retry_after, 1))},
        )


def enforce_rate_limit(policy_factory: Callable[[], RateLimitPolicy]):
    def dependency(
        request: Request,
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        check_rate_limit(
            limiter=limiter,
            policy=policy_factory(),
            identifier=client_identifier(request),
        )

    return dependency


enforce_login_rate_limit = enforce_rate_limit(get_login_rate_limit)
enforce_registration_rate_limit = enforce_rate_limit(get_registration_rate_limit)


def redis_is_ready() -> bool:
    try:
        return bool(get_redis_client().ping())
    except RedisError:
        return False
