"""
User Management API — Super Admin and Admin operations.

Super Admin:
  - Full CRUD on all users
  - Create admins, assign assistants to admins

Admin:
  - List/manage own assistants
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import (
    get_current_user, require_super_admin, require_admin_or_above,
)
from app.models.user import User
from app.schemas.user import (
    UserCreateRequest, UserUpdateRequest,
    UserResponse, UserListResponse,
)
from app.services import user_service as service

router = APIRouter()


# ─── Super Admin endpoints ────────────────────────────────────

@router.get("", response_model=UserListResponse)
async def list_users(
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    return await service.list_users(
        db, search=search, role=role, page=page, page_size=page_size,
    )


@router.get("/admins", response_model=list[UserResponse])
async def list_admins(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    admins = await service.get_admins(db)
    return [UserResponse.model_validate(a) for a in admins]


@router.get("/my-assistants", response_model=list[UserResponse])
async def list_my_assistants(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    """Admin: list assistants assigned to me."""
    assistants = await service.get_assistants_for_admin(db, user.id)
    return [UserResponse.model_validate(a) for a in assistants]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    target = await service.get_user(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(target)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    try:
        new_user = await service.create_user(db, data)
        return UserResponse.model_validate(new_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    if user.role == User.ROLE_ADMIN:
        target = await service.get_user(db, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if target.admin_id != user.id and target.id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Admins can only update their own assistants",
            )
        data.role = None
        data.is_active = None

    updated = await service.update_user(db, user_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(updated)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    try:
        deleted = await service.delete_user(db, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Admin: add assistant ─────────────────────────────────────

@router.post("/assistants", response_model=UserResponse, status_code=201)
async def add_assistant(
    data: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    """Admin: add assistant assigned to self."""
    data.role = "assistant"
    data.admin_id = user.id
    try:
        assistant = await service.create_user(db, data)
        return UserResponse.model_validate(assistant)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
