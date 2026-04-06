from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user, require_admin_or_above
from app.models.user import User
from app.schemas.data_source import (
    DataSourceCreate, DataSourceUpdate, DataSourceResponse,
    DataSourceListResponse, DataSourceStats, ActivityLogResponse,
)
from app.services import data_source_service as service

router = APIRouter()


@router.get("/stats", response_model=DataSourceStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.get_stats(db, user_id=user.id)


@router.get("/activity", response_model=list[ActivityLogResponse])
async def get_activity(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.get_activity_log(db, limit=limit, user_id=user.id)


@router.get("/topics", response_model=list[str])
async def get_topics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.get_topics(db, user_id=user.id)


@router.get("/tags", response_model=list[str])
async def get_tags(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.get_tags(db, user_id=user.id)


@router.get("", response_model=DataSourceListResponse)
async def list_data_sources(
    search: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.list_data_sources(
        db, search=search, topic=topic, page=page, page_size=page_size, user_id=user.id,
    )


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_data_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    source = await service.get_data_source(db, source_id, user_id=user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return DataSourceResponse.model_validate(source)


@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_data_source(
    data: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    source = await service.create_data_source(db, data, user_id=user.id)
    return DataSourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=DataSourceResponse)
async def update_data_source(
    source_id: UUID,
    data: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    source = await service.update_data_source(db, source_id, data, user_id=user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return DataSourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=204)
async def delete_data_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deleted = await service.delete_data_source(db, source_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data source not found")


# ─── Public / Sync Endpoints ─────────────────────────────────

@router.get("/public/list", response_model=DataSourceListResponse)
async def list_public_data_sources(
    search: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    return await service.list_public_data_sources(db, search=search, topic=topic)


@router.post("/public/{source_id}/sync", response_model=DataSourceResponse, status_code=201)
async def sync_public_data_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    try:
        source = await service.sync_public_data_source(db, source_id, user_id=user.id)
        return DataSourceResponse.model_validate(source)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
