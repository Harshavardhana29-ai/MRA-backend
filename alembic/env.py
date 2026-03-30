import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from dotenv import load_dotenv
import os
 
load_dotenv()
 
# this is the Alembic Config object
config = context.config
 
# Override sqlalchemy.url from .env if available
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
 
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
 
# Import all models so Alembic can detect them
from app.database import Base
from app.models.data_source import DataSource
from app.models.agent import Agent, AgentTopicMapping
from app.models.workflow import Workflow, WorkflowDataSource, WorkflowAgent
from app.models.activity_log import ActivityLog
from app.models.run import WorkflowRun, RunLog
 
target_metadata = Base.metadata
 
 
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
 
 
def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
 
 
async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()
 
 
def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
 
 
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()