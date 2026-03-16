from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.agent import AgentResponse, TopicAgentMapResponse
from app.services import agent_service as service

router = APIRouter()


@router.get("", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    return await service.list_agents(db)


@router.get("/by-topics", response_model=list[AgentResponse])
async def get_agents_by_topics(
    topics: list[str] = Query(..., alias="topics"),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_agents_by_topics(db, topics)


@router.get("/topic-mapping", response_model=TopicAgentMapResponse)
async def get_topic_agent_mapping(db: AsyncSession = Depends(get_db)):
    mapping = await service.get_topic_agent_mapping(db)
    return TopicAgentMapResponse(mapping=mapping)
