from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mra_db"
    NEWS_AGENT_API_URL: str = "https://news-agent-gateway-bnwb9717.uc.gateway.dev/ask"
    CORS_ORIGINS: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
