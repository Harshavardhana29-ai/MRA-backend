import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.schemas.user import (
    UserCreateRequest, UserUpdateRequest,
    UserResponse, UserListResponse,
)

logger = logging.getLogger(__name__)


async def list_users(
    db: AsyncSession,
    search: str | None = None,
    role: str | None = None,
    admin_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
) -> UserListResponse:
    query = select(User)

    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                User.display_name.ilike(term),
                User.email.ilike(term),
                User.ntid.ilike(term),
            )
        )
    if role and role != "all":
        query = query.where(User.role == role)
    if admin_id:
        query = query.where(User.admin_id == admin_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
    )


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    data: UserCreateRequest,
) -> User:
    """Create a new user by NTID (Super Admin operation)."""
    ntid_lower = data.ntid.lower().strip()

    existing = await db.execute(select(User).where(User.ntid == ntid_lower))
    if existing.scalar_one_or_none():
        raise ValueError(f"User with NTID '{ntid_lower}' already exists")

    placeholder_email = f"{ntid_lower}@bosch.com"
    user = User(
        id=uuid.uuid4(),
        sso_id=f"pending_{uuid.uuid4().hex[:12]}",
        ntid=ntid_lower,
        email=placeholder_email,
        display_name=data.display_name,
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
        admin_id=data.admin_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    logger.info("Created user ntid=%s (%s) with role %s", ntid_lower, user.id, user.role)
    return user


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: UserUpdateRequest,
) -> User | None:
    user = await get_user(db, user_id)
    if not user:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Updated user %s (%s)", user.email, user.id)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> bool:
    user = await get_user(db, user_id)
    if not user:
        return False

    if user.role == User.ROLE_SUPER_ADMIN:
        raise ValueError("Cannot delete a Super Admin user")

    user.is_active = False
    user.role = User.ROLE_USER
    user.admin_id = None
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Soft-deleted (deactivated) user %s (%s)", user.email, user.id)
    return True


async def get_assistants_for_admin(
    db: AsyncSession, admin_id: uuid.UUID,
) -> list[User]:
    result = await db.execute(
        select(User)
        .where(User.admin_id == admin_id, User.role == User.ROLE_ASSISTANT)
        .order_by(User.display_name)
    )
    return list(result.scalars().all())


async def get_admins(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User)
        .where(User.role == User.ROLE_ADMIN, User.is_active == True)
        .order_by(User.display_name)
    )
    return list(result.scalars().all())
