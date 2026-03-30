import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User, UserSession

logger = logging.getLogger(__name__)
settings = get_settings()


class AuthService:
    """Handles MCP SSO session verification, JWT generation, and DB session management."""

    # ── MCP SSO Verification ──────────────────────────────────────

    @staticmethod
    async def verify_mcp_session(mcp_session_id: str) -> dict:
        """
        Verify an MCP SSO session by calling GET {SSO_MCP_BASE}/sso/me?session_id=xxx.
        Returns user info dict from the MCP SSO service.
        Same API used by myfinance.
        """
        me_url = f"{settings.SSO_MCP_BASE.rstrip('/')}/sso/me"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                me_url,
                params={"session_id": mcp_session_id},
            )

        if response.status_code != 200:
            logger.warning("MCP SSO /sso/me failed: %s", response.text)
            raise ValueError("Invalid or expired MCP session")

        data = response.json()

        if data.get("error"):
            raise ValueError(data.get("message", "MCP session verification failed"))

        user_data = data.get("user", data)
        if not user_data or not user_data.get("sub"):
            raise ValueError("Invalid user data from MCP SSO")

        return user_data

    # ── User Upsert ──────────────────────────────────────────────

    @staticmethod
    async def upsert_user(db: AsyncSession, sso_user: dict) -> User:
        """
        Create or update a user from MCP SSO profile data.
        Maps MCP SSO fields: sub, email, name, ntid, givenName, surname, jobTitle, department
        """
        sso_id = str(sso_user.get("sub") or sso_user.get("id") or sso_user.get("sso_id"))
        email = sso_user.get("email", "")
        display_name = sso_user.get("name") or sso_user.get("display_name") or email.split("@")[0]
        first_name = sso_user.get("givenName") or sso_user.get("given_name") or sso_user.get("first_name")
        last_name = sso_user.get("surname") or sso_user.get("family_name") or sso_user.get("last_name")
        avatar_url = sso_user.get("avatar_url") or sso_user.get("picture")

        stmt = select(User).where(User.sso_id == sso_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if user:
            user.email = email
            user.display_name = display_name
            user.first_name = first_name
            user.last_name = last_name
            user.avatar_url = avatar_url
            user.last_login_at = now
            user.updated_at = now
        else:
            user = User(
                id=uuid.uuid4(),
                sso_id=sso_id,
                email=email,
                display_name=display_name,
                first_name=first_name,
                last_name=last_name,
                avatar_url=avatar_url,
                role="user",
                is_active=True,
                last_login_at=now,
            )
            db.add(user)

        await db.flush()
        return user

    # ── JWT Token ─────────────────────────────────────────────────

    @staticmethod
    def create_access_token(user: User) -> tuple[str, datetime]:
        """
        Generate a JWT access token for the given user.
        Returns (token_string, expiry_datetime).
        """
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "name": user.display_name,
            "role": user.role,
            "iat": datetime.now(timezone.utc),
            "exp": expires_at,
            "jti": uuid.uuid4().hex,
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return token, expires_at

    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and verify a JWT token."""
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

    @staticmethod
    def hash_token(token: str) -> str:
        """SHA-256 hash of a token for DB storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    # ── Session Management ────────────────────────────────────────

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user: User,
        token: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        """Persist a new session record in DB."""
        session = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=AuthService.hash_token(token),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        db.add(session)
        await db.flush()
        return session

    @staticmethod
    async def validate_session(db: AsyncSession, token: str) -> User | None:
        """Validate a JWT token and ensure the session exists in DB."""
        try:
            payload = AuthService.decode_token(token)
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.debug("Invalid token")
            return None

        token_hash = AuthService.hash_token(token)
        stmt = (
            select(UserSession)
            .where(
                UserSession.token_hash == token_hash,
                UserSession.expires_at > datetime.now(timezone.utc),
            )
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if not session:
            return None

        user_id = uuid.UUID(payload["sub"])
        stmt = select(User).where(User.id == user_id, User.is_active == True)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke_session(db: AsyncSession, token: str) -> None:
        """Delete a session (logout)."""
        token_hash = AuthService.hash_token(token)
        stmt = delete(UserSession).where(UserSession.token_hash == token_hash)
        await db.execute(stmt)

    @staticmethod
    async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
        """Delete all sessions for a user."""
        stmt = delete(UserSession).where(UserSession.user_id == user_id)
        await db.execute(stmt)

    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> int:
        """Remove expired sessions. Returns count of deleted rows."""
        stmt = delete(UserSession).where(
            UserSession.expires_at < datetime.now(timezone.utc)
        )
        result = await db.execute(stmt)
        return result.rowcount
