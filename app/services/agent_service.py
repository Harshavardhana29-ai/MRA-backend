from uuid import UUID
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.agent import Agent, AgentTopicMapping
from app.schemas.agent import AgentResponse


async def list_agents(db: AsyncSession) -> list[AgentResponse]:
    result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.topic_mappings))
        .order_by(Agent.name)
    )
    agents = result.scalars().all()
    return [AgentResponse.model_validate(a) for a in agents]


async def get_agents_by_topics(db: AsyncSession, topics: list[str]) -> list[AgentResponse]:
    """Return agents that are mapped to any of the given topics (union)."""
    if not topics:
        return []

    # Get distinct agent IDs for the given topics
    agent_ids_q = (
        select(distinct(AgentTopicMapping.agent_id))
        .where(AgentTopicMapping.topic.in_(topics))
    )
    result = await db.execute(agent_ids_q)
    agent_ids = [row[0] for row in result.all()]

    if not agent_ids:
        return []

    agents_result = await db.execute(
        select(Agent)
        .where(Agent.id.in_(agent_ids))
        .options(selectinload(Agent.topic_mappings))
        .order_by(Agent.name)
    )
    agents = agents_result.scalars().all()
    return [AgentResponse.model_validate(a) for a in agents]


async def get_topic_agent_mapping(db: AsyncSession) -> dict[str, list[AgentResponse]]:
    """Return full topic → agents mapping."""
    result = await db.execute(
        select(AgentTopicMapping)
        .options(selectinload(AgentTopicMapping.agent))
        .order_by(AgentTopicMapping.topic)
    )
    mappings = result.scalars().all()

    topic_map: dict[str, list[AgentResponse]] = {}
    for mapping in mappings:
        if mapping.topic not in topic_map:
            topic_map[mapping.topic] = []
        topic_map[mapping.topic].append(
            AgentResponse.model_validate(mapping.agent)
        )

    return topic_map
