import asyncio
import time
from datetime import datetime, timezone
from uuid import UUID
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.models.run import WorkflowRun, RunLog
from app.models.workflow import Workflow, WorkflowAgent, WorkflowDataSource
from app.models.agent import Agent
from app.models.data_source import DataSource
from app.schemas.run import (
    RunLogResponse, WorkflowRunResponse, RunStartResponse, RunStatusResponse,
)


async def start_run(db: AsyncSession, workflow_id: UUID, user_prompt: str) -> RunStartResponse:
    """Create a new run record and return its ID. Execution happens in background."""
    # Verify workflow exists
    wf = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.deleted_at.is_(None))
    )
    workflow = wf.scalar_one_or_none()
    if not workflow:
        raise ValueError("Workflow not found")

    run = WorkflowRun(
        workflow_id=workflow_id,
        user_prompt=user_prompt,
        status="running",
        progress=0.0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()  # Commit NOW so background task can see the record

    run_id = run.id

    # Launch background execution
    asyncio.create_task(_execute_run(run_id, workflow_id, user_prompt))

    return RunStartResponse(run_id=run_id, status="running")


async def _add_log(db: AsyncSession, run_id: UUID, message: str, log_type: str, elapsed: str):
    log = RunLog(
        run_id=run_id,
        elapsed_time=elapsed,
        message=message,
        log_type=log_type,
    )
    db.add(log)
    await db.flush()


async def _execute_run(run_id: UUID, workflow_id: UUID, user_prompt: str):
    """Background task: call each agent API and build a combined report."""
    start_time = time.monotonic()

    def _elapsed() -> str:
        secs = int(time.monotonic() - start_time)
        return f"{secs // 60:02d}:{secs % 60:02d}"

    async with AsyncSessionLocal() as db:
        try:
            # Fetch workflow with agents and data sources
            result = await db.execute(
                select(Workflow)
                .where(Workflow.id == workflow_id)
                .options(
                    selectinload(Workflow.agent_associations).selectinload(WorkflowAgent.agent),
                    selectinload(Workflow.data_source_associations).selectinload(WorkflowDataSource.data_source),
                )
            )
            workflow = result.scalar_one()

            run_q = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run = run_q.scalar_one()

            agents = [assoc.agent for assoc in workflow.agent_associations if assoc.agent]
            data_sources = [
                assoc.data_source for assoc in workflow.data_source_associations
                if assoc.data_source and assoc.data_source.deleted_at is None
            ]
            total_steps = len(agents) + 3  # init + connect + agents + report gen

            # Step 1: Initialize
            await _add_log(db, run_id, "Initializing workflow execution…", "info", _elapsed())
            run.progress = round((1 / total_steps) * 100, 1)
            await db.commit()
            await asyncio.sleep(1)

            # Step 2: Connect to data sources
            if data_sources:
                ds_names = ", ".join([ds.title for ds in data_sources])
                await _add_log(db, run_id, f"Connecting to data sources: {ds_names}", "info", _elapsed())
                run.progress = round((2 / total_steps) * 100, 1)
                await db.commit()
                await asyncio.sleep(1)

                await _add_log(db, run_id, f"Data source connection established ({len(data_sources)} sources)", "success", _elapsed())
                await db.commit()
            else:
                await _add_log(db, run_id, "Prompt-only mode — no data sources to connect", "info", _elapsed())
                run.progress = round((2 / total_steps) * 100, 1)
                await db.commit()
                await asyncio.sleep(0.5)

            # Step 3: Call each agent
            agent_responses: list[str] = []
            for idx, agent in enumerate(agents):
                step_num = 3 + idx
                await _add_log(
                    db, run_id,
                    f"Agent: {agent.name} — processing…",
                    "info", _elapsed(),
                )
                run.progress = round((step_num / total_steps) * 100, 1)
                await db.commit()

                # Call the agent API if URL is configured
                agent_answer = None
                if agent.api_url:
                    try:
                        async with httpx.AsyncClient(timeout=600.0) as client:
                            # Build the prompt: combine user prompt with data source context
                            prompt = user_prompt or f"Analyze the latest information about {workflow.topic}"
                            if data_sources:
                                source_context = "\n".join([f"- {ds.title} ({ds.url})" for ds in data_sources])
                                prompt = f"{prompt}\n\nData Sources:\n{source_context}"

                            response = await client.post(
                                agent.api_url,
                                json={"question": prompt},
                                headers={"Content-Type": "application/json"},
                            )
                            response.raise_for_status()
                            data = response.json()
                            agent_answer = data.get("answer", "")

                        await _add_log(
                            db, run_id,
                            f"Agent: {agent.name} — completed successfully",
                            "success", _elapsed(),
                        )
                    except Exception as e:
                        await _add_log(
                            db, run_id,
                            f"Agent: {agent.name} — error: {str(e)[:200]}",
                            "error", _elapsed(),
                        )
                else:
                    await _add_log(
                        db, run_id,
                        f"Agent: {agent.name} — skipped (no API URL configured)",
                        "warning", _elapsed(),
                    )

                if agent_answer:
                    agent_responses.append(f"## {agent.name} Analysis\n\n{agent_answer}")

                await db.commit()
                await asyncio.sleep(0.5)

            # Step 4: Generate report
            await _add_log(db, run_id, "Generating output report…", "info", _elapsed())
            await db.commit()
            await asyncio.sleep(1)

            # Combine all agent responses into a report
            if agent_responses:
                report = f"# {workflow.title} — Run Report\n\n"
                report += "\n\n---\n\n".join(agent_responses)
            else:
                report = f"# {workflow.title} — Run Report\n\n"
                report += "No agent responses were collected during this run.\n\n"
                report += "This could be because:\n"
                report += "- No agents have API URLs configured\n"
                report += "- All agent API calls failed\n"

            run.report_markdown = report
            run.progress = 100.0
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)

            await _add_log(db, run_id, "Report generated successfully", "success", _elapsed())
            await _add_log(db, run_id, "Workflow execution completed", "success", _elapsed())
            await db.commit()

        except Exception as e:
            import traceback
            print(f"[RUN {run_id}] Background execution error: {e}")
            traceback.print_exc()
            try:
                run_q = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
                run = run_q.scalar_one_or_none()
                if run:
                    run.status = "failed"
                    run.completed_at = datetime.now(timezone.utc)
                    await _add_log(
                        db, run_id,
                        f"Workflow execution failed: {str(e)[:300]}",
                        "error", _elapsed(),
                    )
                    await db.commit()
                else:
                    print(f"[RUN {run_id}] Could not find run record to mark as failed")
            except Exception as inner_e:
                print(f"[RUN {run_id}] Error while marking run as failed: {inner_e}")


async def get_run(db: AsyncSession, run_id: UUID) -> WorkflowRunResponse | None:
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id)
        .options(selectinload(WorkflowRun.logs))
    )
    run = result.scalar_one_or_none()
    if not run:
        return None

    return WorkflowRunResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        user_prompt=run.user_prompt,
        status=run.status,
        progress=run.progress,
        report_markdown=run.report_markdown,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        logs=[
            RunLogResponse(time=log.elapsed_time, message=log.message, type=log.log_type)
            for log in run.logs
        ],
    )


async def get_run_status(db: AsyncSession, run_id: UUID) -> RunStatusResponse | None:
    result = await db.execute(
        select(WorkflowRun).where(WorkflowRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None

    # Count logs
    from sqlalchemy import func
    log_count_q = await db.execute(
        select(func.count()).where(RunLog.run_id == run_id).select_from(RunLog)
    )
    log_count = log_count_q.scalar() or 0

    return RunStatusResponse(
        id=run.id,
        status=run.status,
        progress=run.progress,
        log_count=log_count,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


async def get_run_logs(db: AsyncSession, run_id: UUID) -> list[RunLogResponse]:
    result = await db.execute(
        select(RunLog)
        .where(RunLog.run_id == run_id)
        .order_by(RunLog.timestamp)
    )
    logs = result.scalars().all()
    return [
        RunLogResponse(time=log.elapsed_time, message=log.message, type=log.log_type)
        for log in logs
    ]


async def get_run_report(db: AsyncSession, run_id: UUID) -> str | None:
    result = await db.execute(
        select(WorkflowRun.report_markdown).where(WorkflowRun.id == run_id)
    )
    row = result.scalar_one_or_none()
    return row
