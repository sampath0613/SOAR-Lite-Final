"""
SOAR-Lite FastAPI application factory and lifespan management.
Initializes database, loads playbooks, and registers routers.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from soar.connectors.registry import init_connectors
from soar.db.database import init_db, close_db

logger = logging.getLogger(__name__)

# Global state (populated on startup)
APP_STATE = {
    "playbooks":  {},
    "engine_tasks": {},  # Track background playbook execution tasks
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    FastAPI lifespan context manager.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info("Starting SOAR-Lite...")

    try:
        # Initialize database
        await init_db()

        # Initialize connectors
        init_connectors()

        # Load playbooks
        from soar.engine.parser import load_all_playbooks
        from pathlib import Path

        playbooks_dir = Path(__file__).parent.parent / "playbooks"
        try:
            APP_STATE["playbooks"] = await load_all_playbooks(playbooks_dir)
            logger.info(f"Loaded {len(APP_STATE['playbooks'])} playbooks")
        except Exception as error:
            logger.warning(f"Failed to load playbooks: {error}. Continuing without playbooks.")

        logger.info("SOAR-Lite startup completed")

    except Exception as error:
        logger.error(f"Startup failed: {error}")
        raise

    # Yield to run app
    yield

    # Shutdown
    logger.info("Shutting down SOAR-Lite...")
    await close_db()
    logger.info("SOAR-Lite shutdown completed")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="SOAR-Lite",
        description="Security Orchestration, Automation and Response Engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware (allow all for MVP)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from soar.api.alerts import router as alerts_router
    from soar.api.incidents import router as incidents_router
    from soar.api.playbooks import router as playbooks_router
    from soar.api.analytics import router as analytics_router
    from soar.api.health import router as health_router
    from soar.api.dashboard import router as dashboard_router

    app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
    app.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
    app.include_router(playbooks_router, prefix="/playbooks", tags=["playbooks"])
    app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(dashboard_router, tags=["dashboard"])

    dashboard_static_dir = Path(__file__).resolve().parent.parent / "dashboard" / "static"
    app.mount(
        "/dashboard/static",
        StaticFiles(directory=str(dashboard_static_dir)),
        name="dashboard-static",
    )

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": "SOAR-Lite",
            "version": "0.1.0",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app


# Create app instance for uvicorn
app = create_app()
