from fastapi import Depends, HTTPException, Request, status

from auth.dependencies import get_current_user
from core.rate_limiter import SlidingWindowRateLimiter
from db.models import User

rate_limiter = SlidingWindowRateLimiter()

RATE_LIMITS: dict[str, tuple[int, int]] = {
    "chat": (60, 60),
    "auth": (20, 60),
    "api": (200, 60),
    "admin": (100, 60),
}


async def rate_limit_chat(request: Request):
    user_id = request.state.user_id if hasattr(request.state, "user_id") else "anonymous"
    allowed, remaining, retry_after = await rate_limiter.check(
        f"chat:{user_id}", *RATE_LIMITS["chat"]
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after}s",
            headers={"Retry-After": str(retry_after)},
        )
    return True


async def rate_limit_auth(request: Request):
    ip = request.client.host if request.client else "unknown"
    allowed, remaining, retry_after = await rate_limiter.check(
        f"auth:{ip}", *RATE_LIMITS["auth"]
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many auth attempts. Please wait before trying again.",
            headers={"Retry-After": str(retry_after)},
        )
    return True


async def rate_limit_api(request: Request):
    user_id = "anonymous"
    if hasattr(request.state, "user_id"):
        user_id = request.state.user_id
    allowed, remaining, retry_after = await rate_limiter.check(
        f"api:{user_id}", *RATE_LIMITS["api"]
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
    return True


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
