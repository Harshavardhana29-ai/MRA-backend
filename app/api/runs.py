from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.run import (
    RunWorkflowRequest, RunStartResponse, RunStatusResponse,
    RunLogResponse, WorkflowRunResponse,
)
from app.services import run_service as service

router = APIRouter()


@router.post("/workflow/{workflow_id}/run", response_model=RunStartResponse, status_code=202)
async def run_workflow(
    workflow_id: UUID,
    data: RunWorkflowRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.start_run(db, workflow_id, data.user_prompt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{run_id}", response_model=WorkflowRunResponse)
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)):
    run = await service.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: UUID, db: AsyncSession = Depends(get_db)):
    status = await service.get_run_status(db, run_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found")
    return status


@router.get("/{run_id}/logs", response_model=list[RunLogResponse])
async def get_run_logs(run_id: UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_run_logs(db, run_id)


@router.get("/{run_id}/report")
async def get_run_report(run_id: UUID, db: AsyncSession = Depends(get_db)):
    report = await service.get_run_report(db, run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or run not completed")
    return {"report_markdown": report}
