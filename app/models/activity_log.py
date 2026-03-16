import uuid
from sqlalchemy import Column, String, Text, DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action = Column(String(20), nullable=False)  # Added, Updated, Removed
    entity_type = Column(String(50), nullable=False)  # data_source, workflow
    entity_name = Column(String(500), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_activity_log_timestamp", "timestamp"),
    )
