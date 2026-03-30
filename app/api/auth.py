"""
Auth API — MCP SSO integration with local user + session management.

Flow:
1. Frontend handles SSO login via MCP SSO service (same as myfinance)
2. After SSO callback, frontend calls POST /api/auth/sso/sync with MCP session_id
3. Backend verifies via MCP /sso/me, upserts user in DB, creates local JWT session
4. All subsequent API calls use our local JWT in Authorization header
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.user import (
    AuthTokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


class SSOSyncRequest(BaseModel):
    """Request body for syncing an MCP SSO session with our backend."""
    mcp_session_id: str


@router.post("/sso/sync", response_model=AuthTokenResponse)
async def sso_sync(
    body: SSOSyncRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync MCP SSO session with our backend.
    
    1. Verifies the MCP session_id by calling MCP SSO /sso/me
    2. Upserts user in our DB
    3. Creates a local JWT session
    4. Returns our JWT + user info
    """
    try:
        sso_user = await AuthService.verify_mcp_session(body.mcp_session_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception:
        logger.exception("MCP SSO verification error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SSO service unavailable",
        )

    # Upsert user in DB
    try:
        user = await AuthService.upsert_user(db, sso_user)
    except Exception:
        logger.exception("User upsert failed")
        raise HTTPException(status_code=500, detail="Failed to create/update user")

    # Create local JWT and session
    token, expires_at = AuthService.create_access_token(user)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    await AuthService.create_session(db, user, token, expires_at, ip, ua)

    await db.commit()

    logger.info("SSO sync successful for user %s (%s)", user.email, user.id)

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRY_HOURS * 3600,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current local session."""
    forwarded = request.headers.get("x-forwarded-authorization", "")
    auth_header = forwarded if forwarded.lower().startswith("bearer ") else request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "").replace("bearer ", "").strip()
    await AuthService.revoke_session(db, token)
    await db.commit()


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions for the current user."""
    await AuthService.revoke_all_sessions(db, user.id)
    await db.commit()
