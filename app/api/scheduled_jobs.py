from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.scheduled_job import (
    ScheduledJobCreate, ScheduledJobUpdate, ScheduledJobResponse,
    JobHistoryResponse, JobCountsResponse, RecentRunResponse,
)
from app.services import scheduler_service as service

router = APIRouter()


@router.get("/jobs", response_model=list[ScheduledJobResponse])
async def list_jobs(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_jobs(db, status)


@router.get("/jobs/counts", response_model=JobCountsResponse)
async def get_counts(db: AsyncSession = Depends(get_db)):
    return await service.get_counts(db)


@router.post("/jobs", response_model=ScheduledJobResponse, status_code=201)
async def create_job(
    data: ScheduledJobCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.create_job(db, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}", response_model=ScheduledJobResponse)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await service.get_job(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/jobs/{job_id}", response_model=ScheduledJobResponse)
async def update_job(
    job_id: UUID,
    data: ScheduledJobUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.update_job(db, job_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        await service.delete_job(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/toggle", response_model=ScheduledJobResponse)
async def toggle_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await service.toggle_job(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}/history", response_model=list[JobHistoryResponse])
async def get_job_history(job_id: UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_job_history(db, job_id)


@router.get("/recent-runs", response_model=list[RecentRunResponse])
async def get_recent_runs(db: AsyncSession = Depends(get_db)):
    return await service.get_recent_runs(db)
