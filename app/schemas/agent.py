from pydantic import BaseModel
from uuid import UUID


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    api_url: str | None = None
    api_method: str
    is_active: str

    model_config = {"from_attributes": True}


class AgentTopicMappingResponse(BaseModel):
    topic: str
    agents: list[str]


class TopicAgentMapResponse(BaseModel):
    mapping: dict[str, list[AgentResponse]]
