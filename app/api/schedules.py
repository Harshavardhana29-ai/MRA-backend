from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.schedule import (
    ScheduledJobCreate, ScheduledJobUpdate, ScheduledJobResponse,
    ScheduledJobListResponse, ScheduledJobStats,
    JobHistoryResponse,
)
from app.services import schedule_service as service

router = APIRouter()


@router.get("/stats", response_model=ScheduledJobStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await service.get_stats(db)


@router.get("", response_model=ScheduledJobListResponse)
async def list_jobs(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_jobs(db, status=status, search=search)


@router.get("/{job_id}", response_model=ScheduledJobResponse)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    job = await service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    return job


@router.post("", response_model=ScheduledJobResponse, status_code=201)
async def create_job(
    data: ScheduledJobCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.create_job(db, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{job_id}", response_model=ScheduledJobResponse)
async def update_job(
    job_id: UUID,
    data: ScheduledJobUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await service.update_job(db, job_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    return job


@router.post("/{job_id}/toggle", response_model=ScheduledJobResponse)
async def toggle_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    job = await service.toggle_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    deleted = await service.delete_job(db, job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scheduled job not found")


@router.get("/{job_id}/history", response_model=list[JobHistoryResponse])
async def get_history(
    job_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_history(db, job_id, limit=limit)
