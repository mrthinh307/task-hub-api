from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Task Hub API"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # NeonDB PostgreSQL 16 connection URL
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/neondb",
        description="Async PostgreSQL connection string",
    )

    # Redis connection URL
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()
