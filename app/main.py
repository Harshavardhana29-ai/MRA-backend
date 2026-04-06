import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api import auth, data_sources, workflows, agents, runs, scheduled_jobs, chat, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s — %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.scheduler_service import start_scheduler, stop_scheduler
    await start_scheduler()
    yield
    await stop_scheduler()


app = FastAPI(
    title="MRA Backend",
    description="Market Research Agent — Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(data_sources.router, prefix="/api/data-sources", tags=["Data Sources"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(runs.router, prefix="/api/runs", tags=["Runs"])
app.include_router(scheduled_jobs.router, prefix="/api/scheduler", tags=["Scheduler"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
