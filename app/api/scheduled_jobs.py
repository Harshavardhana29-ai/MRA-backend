from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user, get_effective_user_id
from app.models.user import User
from app.schemas.scheduled_job import (
    ScheduledJobCreate, ScheduledJobUpdate, ScheduledJobResponse,
    ScheduledJobListResponse, JobHistoryResponse, JobCountsResponse, RecentRunResponse,
)
from app.services import scheduler_service as service

router = APIRouter()


@router.get("/jobs", response_model=ScheduledJobListResponse)
async def list_jobs(
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.list_jobs(
        db, status_filter=status, search=search, page=page, page_size=page_size,
        user_id=get_effective_user_id(user),
    )


@router.get("/jobs/counts", response_model=JobCountsResponse)
async def get_counts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.get_counts(db, user_id=get_effective_user_id(user))


@router.post("/jobs", response_model=ScheduledJobResponse, status_code=201)
async def create_job(
    data: ScheduledJobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await service.create_job(db, data, user_id=get_effective_user_id(user))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}", response_model=ScheduledJobResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await service.get_job(db, job_id, user_id=get_effective_user_id(user))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/jobs/{job_id}", response_model=ScheduledJobResponse)
async def update_job(
    job_id: UUID,
    data: ScheduledJobUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await service.update_job(db, job_id, data, user_id=get_effective_user_id(user))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        await service.delete_job(db, job_id, user_id=get_effective_user_id(user))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/toggle", response_model=ScheduledJobResponse)
async def toggle_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return await service.toggle_job(db, job_id, user_id=get_effective_user_id(user))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}/history", response_model=list[JobHistoryResponse])
async def get_job_history(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.get_job_history(db, job_id, user_id=get_effective_user_id(user))


@router.get("/recent-runs", response_model=list[RecentRunResponse])
async def get_recent_runs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await service.get_recent_runs(db, user_id=get_effective_user_id(user))
