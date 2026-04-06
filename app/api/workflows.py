from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user, require_admin_or_above, get_effective_user_id
from app.models.user import User
from app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse,
    WorkflowListResponse, WorkflowStats,
)
from app.services import workflow_service as service

router = APIRouter()


@router.get("/stats", response_model=WorkflowStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.get_stats(db, user_id=get_effective_user_id(user))


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    topic: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.list_workflows(
        db, topic=topic, search=search, page=page, page_size=page_size,
        user_id=get_effective_user_id(user),
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = await service.get_workflow(db, workflow_id, user_id=get_effective_user_id(user))
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.create_workflow(db, data, user_id=get_effective_user_id(user))


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = await service.update_workflow(db, workflow_id, data, user_id=get_effective_user_id(user))
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deleted = await service.delete_workflow(db, workflow_id, user_id=get_effective_user_id(user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")


# ─── Public / Sync Endpoints ─────────────────────────────────

@router.get("/public/list", response_model=WorkflowListResponse)
async def list_public_workflows(
    topic: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.list_public_workflows(db, topic=topic)


@router.post("/public/{workflow_id}/sync", response_model=WorkflowResponse, status_code=201)
async def sync_public_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await service.sync_public_workflow(db, workflow_id, user_id=get_effective_user_id(user))
    except ValueError as e:
        detail = str(e)
        code = 409 if "already been synced" in detail else 404
        raise HTTPException(status_code=code, detail=detail)
