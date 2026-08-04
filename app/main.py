from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_handlers import register_exception_handlers
from app.api.v1.api import api_router
from app.core.background import BackgroundTaskDispatcher
from app.core.config import settings
from app.core.logging import logger
from app.db.session import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager.

    Manages application lifecycle events:
    - Code BEFORE `yield` executes on application STARTUP.
    - Code AFTER `yield` executes on application SHUTDOWN.
    """
    # 1. STARTUP: Initialize Redis connections and shared resources
    logger.info(f"Starting {settings.PROJECT_NAME}...")
    await init_redis()

    # Yield control to FastAPI app to handle incoming HTTP requests
    yield

    # 2. SHUTDOWN: Gracefully clean up resources and close connections
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    await app.state.background_dispatcher.shutdown(
        settings.BACKGROUND_TASK_SHUTDOWN_TIMEOUT_SECONDS
    )
    await close_redis()


def create_app() -> FastAPI:
    """
    Application Factory Function.

    Instantiates and configures the main FastAPI application instance:
    - Metadata & OpenAPI Swagger Docs configuration
    - Lifespan Manager registration
    - CORS Middleware configuration
    - API Routers v1 registration
    - Health Check Endpoint definition
    """
    # Instantiate the primary FastAPI application instance
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.background_dispatcher = BackgroundTaskDispatcher()

    # Configure CORS (Cross-Origin Resource Sharing) Middleware
    # Allows cross-origin requests from frontend applications
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Include API v1 router aggregator with prefix (e.g., `/api/v1`)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # System Health Check Endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "project": settings.PROJECT_NAME}

    return app


# Create official FastAPI app instance (invoked by Uvicorn via `app.main:app`)
app = create_app()
