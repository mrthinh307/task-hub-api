import asyncio
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import logger

# Create the SQLAlchemy async engine for PostgreSQL running in Docker.
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Redis connection pool
redis_client: aioredis.Redis | None = None
redis_init_lock = asyncio.Lock()


async def init_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is not None:
        return redis_client

    async with redis_init_lock:
        if redis_client is not None:
            return redis_client

        client: aioredis.Redis | None = None
        try:
            client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,
                retry_on_timeout=True,
            )
            await client.ping()
        except Exception:
            if client is not None:
                await client.aclose()
            logger.exception("Failed to initialize Redis connection.")
            raise

        redis_client = client
        logger.info("Redis connection initialized successfully.")
        return client


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
        logger.info("Redis connection closed.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing asynchronous SQLAlchemy database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Dependency for providing asynchronous Redis connection."""
    client = await init_redis()
    yield client
