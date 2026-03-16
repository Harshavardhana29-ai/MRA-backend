from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from uuid import UUID


# --- Request schemas ---

class DataSourceCreate(BaseModel):
    url: str = Field(..., min_length=1, max_length=2000)
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    topic: str = Field(..., min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list)


class DataSourceUpdate(BaseModel):
    url: str | None = None
    title: str | None = None
    description: str | None = None
    topic: str | None = None
    tags: list[str] | None = None
    status: str | None = None


# --- Response schemas ---

class DataSourceResponse(BaseModel):
    id: UUID
    url: str
    title: str
    description: str | None = None
    topic: str
    tags: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    # Frontend compatibility aliases
    @property
    def name(self) -> str:
        return self.title

    @property
    def type(self) -> str:
        return "URL"

    @property
    def uploadDate(self) -> str:
        return self.created_at.strftime("%Y-%m-%d")

    model_config = {"from_attributes": True}


class DataSourceListResponse(BaseModel):
    items: list[DataSourceResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DataSourceStats(BaseModel):
    total_sources: int
    topic_count: int


class ActivityLogResponse(BaseModel):
    action: str
    source: str
    time: str  # relative time string
    color: str

    model_config = {"from_attributes": True}
