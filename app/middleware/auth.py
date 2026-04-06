"""
FastAPI dependencies for authenticating requests via JWT Bearer token
and enforcing role-based access control.

Usage:
    @router.get("/protected")
    async def protected(user: User = Depends(get_current_user)):
        ...

    @router.get("/admin-only")
    async def admin_only(user: User = Depends(require_super_admin)):
        ...
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def _extract_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    """
    GCP API Gateway replaces the Authorization header with its own JWT
    for backend auth and moves the original client token to
    X-Forwarded-Authorization. Check that header first.
    """
    forwarded = request.headers.get("x-forwarded-authorization", "")
    if forwarded.lower().startswith("bearer "):
        return forwarded[7:].strip()
    if credentials:
        return credentials.credentials
    return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract the Bearer token, validate it, and return the authenticated User.
    Raises 401 if unauthenticated.
    """
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await AuthService.validate_session(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Same as get_current_user but returns None instead of 401."""
    token = _extract_token(request, credentials)
    if not token:
        return None
    return await AuthService.validate_session(db, token)


# ─── Role-Based Permission Dependencies ──────────────────────

async def require_assigned_user(
    user: User = Depends(get_current_user),
) -> User:
    """Requires the user to have an assigned role (not 'user')."""
    if not user.is_assigned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted — you have not been assigned a role",
        )
    return user


async def require_super_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Only super_admin can access this endpoint."""
    if user.role != User.ROLE_SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required",
        )
    return user


async def require_admin_or_above(
    user: User = Depends(get_current_user),
) -> User:
    """super_admin or admin can access this endpoint."""
    if user.role not in (User.ROLE_SUPER_ADMIN, User.ROLE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
