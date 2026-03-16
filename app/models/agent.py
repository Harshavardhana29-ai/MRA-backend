import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    api_url = Column(Text, nullable=True)
    api_method = Column(String(10), nullable=False, default="POST")
    is_active = Column(String(10), nullable=False, default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    topic_mappings = relationship("AgentTopicMapping", back_populates="agent", cascade="all, delete-orphan")
    workflow_associations = relationship("WorkflowAgent", back_populates="agent", passive_deletes=True)

    __table_args__ = (
        Index("idx_agent_name", "name"),
    )


class AgentTopicMapping(Base):
    __tablename__ = "agent_topic_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String(100), nullable=False)

    # Relationship
    agent = relationship("Agent", back_populates="topic_mappings")

    __table_args__ = (
        Index("idx_agent_topic_mapping_topic", "topic"),
        Index("idx_agent_topic_mapping_unique", "agent_id", "topic", unique=True),
    )
