from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.workflow import Workflow, WorkflowDataSource, WorkflowAgent
from app.models.data_source import DataSource
from app.models.agent import Agent
from app.models.activity_log import ActivityLog
from app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse,
    WorkflowListResponse, WorkflowStats,
    WorkflowDataSourceResponse, WorkflowAgentResponse,
)


def _build_workflow_response(workflow: Workflow) -> WorkflowResponse:
    data_sources = [
        WorkflowDataSourceResponse(
            id=assoc.data_source.id,
            title=assoc.data_source.title,
            topic=assoc.data_source.topic,
        )
        for assoc in workflow.data_source_associations
        if assoc.data_source and assoc.data_source.deleted_at is None
    ]
    agents = [
        WorkflowAgentResponse(id=assoc.agent.id, name=assoc.agent.name)
        for assoc in workflow.agent_associations
        if assoc.agent
    ]
    return WorkflowResponse(
        id=workflow.id,
        title=workflow.title,
        topic=workflow.topic,
        status=workflow.status,
        source_selection_mode=workflow.source_selection_mode,
        selected_topics=workflow.selected_topics or [],
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        data_sources=data_sources,
        agents=agents,
    )


def _workflow_query():
    return (
        select(Workflow)
        .where(Workflow.deleted_at.is_(None))
        .options(
            selectinload(Workflow.data_source_associations).selectinload(WorkflowDataSource.data_source),
            selectinload(Workflow.agent_associations).selectinload(WorkflowAgent.agent),
        )
    )


async def create_workflow(
    db: AsyncSession, data: WorkflowCreate, user_id: UUID | None = None,
) -> WorkflowResponse:
    workflow = Workflow(
        user_id=user_id,
        title=data.title,
        topic=data.topic,
        status=data.status,
        source_selection_mode=data.source_selection_mode,
        selected_topics=data.selected_topics,
    )
    db.add(workflow)
    await db.flush()

    # Add data source associations
    for ds_id in data.data_source_ids:
        assoc = WorkflowDataSource(workflow_id=workflow.id, data_source_id=ds_id)
        db.add(assoc)

    # Add agent associations
    for agent_id in data.agent_ids:
        assoc = WorkflowAgent(workflow_id=workflow.id, agent_id=agent_id)
        db.add(assoc)

    await db.flush()

    # Log activity
    log = ActivityLog(
        user_id=user_id,
        action="Added",
        entity_type="workflow",
        entity_name=data.title,
    )
    db.add(log)
    await db.flush()

    # Re-fetch with relationships
    result = await db.execute(_workflow_query().where(Workflow.id == workflow.id))
    workflow = result.scalar_one()
    return _build_workflow_response(workflow)


async def get_workflow(
    db: AsyncSession, workflow_id: UUID, user_id: UUID | None = None,
) -> WorkflowResponse | None:
    query = _workflow_query().where(Workflow.id == workflow_id)
    if user_id:
        query = query.where(Workflow.user_id == user_id)
    result = await db.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow:
        return None
    return _build_workflow_response(workflow)


async def list_workflows(
    db: AsyncSession,
    topic: str | None = None,
    user_id: UUID | None = None,
) -> WorkflowListResponse:
    query = _workflow_query()
    if user_id:
        query = query.where(Workflow.user_id == user_id)

    if topic and topic.lower() != "all":
        query = query.where(Workflow.topic == topic)

    query = query.order_by(Workflow.created_at.desc())
    result = await db.execute(query)
    workflows = result.scalars().unique().all()

    items = [_build_workflow_response(w) for w in workflows]
    return WorkflowListResponse(items=items, total=len(items))


async def update_workflow(
    db: AsyncSession, workflow_id: UUID, data: WorkflowUpdate, user_id: UUID | None = None,
) -> WorkflowResponse | None:
    query = select(Workflow).where(
        Workflow.id == workflow_id,
        Workflow.deleted_at.is_(None),
    )
    if user_id:
        query = query.where(Workflow.user_id == user_id)
    result = await db.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow:
        return None

    # Update scalar fields
    update_data = data.model_dump(exclude_unset=True, exclude={"data_source_ids", "agent_ids"})
    for key, value in update_data.items():
        setattr(workflow, key, value)
    workflow.updated_at = datetime.now(timezone.utc)

    # Update data source associations if provided
    if data.data_source_ids is not None:
        # Remove existing
        await db.execute(
            WorkflowDataSource.__table__.delete().where(
                WorkflowDataSource.workflow_id == workflow_id
            )
        )
        for ds_id in data.data_source_ids:
            db.add(WorkflowDataSource(workflow_id=workflow_id, data_source_id=ds_id))

    # Update agent associations if provided
    if data.agent_ids is not None:
        await db.execute(
            WorkflowAgent.__table__.delete().where(
                WorkflowAgent.workflow_id == workflow_id
            )
        )
        for agent_id in data.agent_ids:
            db.add(WorkflowAgent(workflow_id=workflow_id, agent_id=agent_id))

    await db.flush()

    # Log activity
    log = ActivityLog(
        user_id=user_id,
        action="Updated",
        entity_type="workflow",
        entity_name=workflow.title,
    )
    db.add(log)
    await db.flush()

    # Re-fetch with relationships
    result = await db.execute(_workflow_query().where(Workflow.id == workflow_id))
    workflow = result.scalar_one()
    return _build_workflow_response(workflow)


async def delete_workflow(
    db: AsyncSession, workflow_id: UUID, user_id: UUID | None = None,
) -> bool:
    query = select(Workflow).where(
        Workflow.id == workflow_id,
        Workflow.deleted_at.is_(None),
    )
    if user_id:
        query = query.where(Workflow.user_id == user_id)
    result = await db.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow:
        return False

    workflow.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    log = ActivityLog(
        user_id=user_id,
        action="Removed",
        entity_type="workflow",
        entity_name=workflow.title,
    )
    db.add(log)
    await db.flush()

    return True


async def get_stats(db: AsyncSession, user_id: UUID | None = None) -> WorkflowStats:
    # Total active workflows
    total_q = select(func.count()).where(Workflow.deleted_at.is_(None))
    if user_id:
        total_q = total_q.where(Workflow.user_id == user_id)
    total = (await db.execute(total_q)).scalar() or 0

    # Count distinct agents used across all active workflows
    agents_q = (
        select(func.count(distinct(WorkflowAgent.agent_id)))
        .select_from(WorkflowAgent)
        .join(Workflow, WorkflowAgent.workflow_id == Workflow.id)
        .where(Workflow.deleted_at.is_(None))
    )
    if user_id:
        agents_q = agents_q.where(Workflow.user_id == user_id)
    agents_used = (await db.execute(agents_q)).scalar() or 0

    return WorkflowStats(total=total, agents_used=agents_used)
