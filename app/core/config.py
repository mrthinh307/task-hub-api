from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Taskhub"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    DATABASE_URL: str = Field(..., description="Async PostgreSQL connection string")

    # Redis connection URL
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_CONNECT_TIMEOUT: float = 2.0
    REDIS_SOCKET_TIMEOUT: float = 5.0
    REDIS_HEALTH_CHECK_INTERVAL: int = 30
    TASK_LIST_CACHE_TTL_SECONDS: int = Field(default=60, ge=1, le=3600)

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith(
                "postgresql+asyncpg://"
            ):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)

            # Clean query params incompatible with asyncpg (channel_binding, sslmode)
            parsed = urlparse(v)
            if parsed.query:
                query_params = parse_qs(parsed.query)
                query_params.pop("channel_binding", None)
                if "sslmode" in query_params:
                    ssl_val = query_params.pop("sslmode")[0]
                    if "ssl" not in query_params:
                        query_params["ssl"] = [ssl_val]

                new_query = urlencode(query_params, doseq=True)
                v = urlunparse(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        new_query,
                        parsed.fragment,
                    )
                )
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()  # pyright: ignore[reportCallIssue]
