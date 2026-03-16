from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.data_source import (
    DataSourceCreate, DataSourceUpdate, DataSourceResponse,
    DataSourceListResponse, DataSourceStats, ActivityLogResponse,
)
from app.services import data_source_service as service

router = APIRouter()


@router.get("/stats", response_model=DataSourceStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await service.get_stats(db)


@router.get("/activity", response_model=list[ActivityLogResponse])
async def get_activity(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_activity_log(db, limit=limit)


@router.get("/topics", response_model=list[str])
async def get_topics(db: AsyncSession = Depends(get_db)):
    return await service.get_topics(db)


@router.get("/tags", response_model=list[str])
async def get_tags(db: AsyncSession = Depends(get_db)):
    return await service.get_tags(db)


@router.get("", response_model=DataSourceListResponse)
async def list_data_sources(
    search: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_data_sources(db, search=search, topic=topic, page=page, page_size=page_size)


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_data_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    source = await service.get_data_source(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return DataSourceResponse.model_validate(source)


@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_data_source(
    data: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
):
    source = await service.create_data_source(db, data)
    return DataSourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=DataSourceResponse)
async def update_data_source(
    source_id: UUID,
    data: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    source = await service.update_data_source(db, source_id, data)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return DataSourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=204)
async def delete_data_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    deleted = await service.delete_data_source(db, source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data source not found")
