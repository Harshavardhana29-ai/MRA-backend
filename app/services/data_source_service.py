from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func, distinct, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.data_source import DataSource
from app.models.activity_log import ActivityLog
from app.schemas.data_source import (
    DataSourceCreate, DataSourceUpdate, DataSourceResponse,
    DataSourceListResponse, DataSourceStats, ActivityLogResponse,
)


PREDEFINED_TOPICS = ["AI", "News", "Sports", "Finance", "Technology", "General", "Healthcare", "Energy", "Automotive"]
PREDEFINED_TAGS = [
    "Research", "News", "Analytics", "API", "Report",
    "Academic", "Real-time", "Historical", "Trends",
    "Market Data", "Open Source", "Enterprise",
]


def _relative_time(dt: datetime) -> str:
    """Convert a datetime to a human-readable relative time string."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    return f"{months} month{'s' if months != 1 else ''} ago"


def _action_color(action: str) -> str:
    colors = {
        "Added": "bg-bosch-green",
        "Updated": "bg-bosch-blue",
        "Removed": "bg-bosch-red",
    }
    return colors.get(action, "bg-bosch-blue")


async def create_data_source(
    db: AsyncSession, data: DataSourceCreate, user_id: UUID | None = None,
) -> DataSource:
    source = DataSource(
        user_id=user_id,
        url=data.url,
        title=data.title,
        description=data.description,
        topic=data.topic,
        tags=data.tags,
        status="Active",
    )
    db.add(source)
    await db.flush()

    # Log activity
    log = ActivityLog(
        user_id=user_id,
        action="Added",
        entity_type="data_source",
        entity_name=data.title,
    )
    db.add(log)
    await db.flush()

    return source


async def get_data_source(
    db: AsyncSession, source_id: UUID, user_id: UUID | None = None,
) -> DataSource | None:
    query = select(DataSource).where(
        DataSource.id == source_id,
        DataSource.deleted_at.is_(None),
    )
    if user_id:
        query = query.where(DataSource.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_data_sources(
    db: AsyncSession,
    search: str | None = None,
    topic: str | None = None,
    page: int = 1,
    page_size: int = 50,
    user_id: UUID | None = None,
) -> DataSourceListResponse:
    query = select(DataSource).where(DataSource.deleted_at.is_(None))
    if user_id:
        query = query.where(DataSource.user_id == user_id)

    if search:
        query = query.where(DataSource.title.ilike(f"%{search}%"))
    if topic and topic != "All":
        query = query.where(DataSource.topic == topic)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(DataSource.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    pages = max(1, (total + page_size - 1) // page_size)

    return DataSourceListResponse(
        items=[DataSourceResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


async def update_data_source(
    db: AsyncSession, source_id: UUID, data: DataSourceUpdate, user_id: UUID | None = None,
) -> DataSource | None:
    source = await get_data_source(db, source_id, user_id=user_id)
    if not source:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(source, key, value)

    source.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Log activity
    log = ActivityLog(
        user_id=user_id,
        action="Updated",
        entity_type="data_source",
        entity_name=source.title,
    )
    db.add(log)
    await db.flush()

    return source


async def delete_data_source(
    db: AsyncSession, source_id: UUID, user_id: UUID | None = None,
) -> bool:
    source = await get_data_source(db, source_id, user_id=user_id)
    if not source:
        return False

    source.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    # Log activity
    log = ActivityLog(
        user_id=user_id,
        action="Removed",
        entity_type="data_source",
        entity_name=source.title,
    )
    db.add(log)
    await db.flush()

    return True


async def get_stats(db: AsyncSession, user_id: UUID | None = None) -> DataSourceStats:
    base = select(DataSource).where(DataSource.deleted_at.is_(None))
    if user_id:
        base = base.where(DataSource.user_id == user_id)

    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    topic_base = select(distinct(DataSource.topic)).where(DataSource.deleted_at.is_(None))
    if user_id:
        topic_base = topic_base.where(DataSource.user_id == user_id)
    topic_count = (await db.execute(select(func.count()).select_from(topic_base.subquery()))).scalar() or 0

    return DataSourceStats(total_sources=total, topic_count=topic_count)


async def get_activity_log(
    db: AsyncSession, limit: int = 10, user_id: UUID | None = None,
) -> list[ActivityLogResponse]:
    query = select(ActivityLog)
    if user_id:
        query = query.where(ActivityLog.user_id == user_id)
    query = query.order_by(ActivityLog.timestamp.desc()).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        ActivityLogResponse(
            action=log.action,
            source=log.entity_name,
            time=_relative_time(log.timestamp),
            color=_action_color(log.action),
        )
        for log in logs
    ]


async def get_topics(db: AsyncSession, user_id: UUID | None = None) -> list[str]:
    query = select(distinct(DataSource.topic)).where(DataSource.deleted_at.is_(None))
    if user_id:
        query = query.where(DataSource.user_id == user_id)
    result = await db.execute(query)
    db_topics = [row[0] for row in result.all()]
    all_topics = list(set(PREDEFINED_TOPICS + db_topics))
    all_topics.sort()
    return all_topics


async def get_tags(db: AsyncSession, user_id: UUID | None = None) -> list[str]:
    # Get all unique tags from data sources (tags is ARRAY column)
    query = select(func.unnest(DataSource.tags).label("tag")).where(DataSource.deleted_at.is_(None))
    if user_id:
        query = query.where(DataSource.user_id == user_id)
    result = await db.execute(query.distinct())
    db_tags = [row[0] for row in result.all()]
    all_tags = list(set(PREDEFINED_TAGS + db_tags))
    all_tags.sort()
    return all_tags
