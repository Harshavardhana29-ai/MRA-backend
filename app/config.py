from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mra_db"
    NEWS_AGENT_API_URL: str = "https://news-agent-gateway-bnwb9717.uc.gateway.dev/ask"
    CORS_ORIGINS: str = "http://127.0.0.1:3000,http://localhost:3000"

    # SSO / Auth
    SSO_MCP_BASE: str = "https://bdo-saarthi-sso-mcp-dev.azurewebsites.net"
    JWT_SECRET: str = "change-me-to-a-random-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
