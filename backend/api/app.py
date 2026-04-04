"""
app.py — FastAPI application factory

Creates and configures the FastAPI app with CORS, routes, and
lifecycle hooks.

The server boots idle — the frontend sends POST /api/start with
config to launch the watcher pipeline.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="PDX Save Analyzer",
        description="Live watcher and analyzer for Paradox game saves",
        version="0.1.0",
    )

    # CORS — allow the React dev server (Vite default port)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",    # Vite dev
            "http://localhost:3000",    # alt dev port
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router)

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("PDX Save Analyzer API started. Waiting for POST /api/start.")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        # If pipeline is running, stop it gracefully
        from backend.api.routes import _pipeline
        if _pipeline and _pipeline.is_running:
            logger.info("Shutting down pipeline...")
            await _pipeline.stop()
        logger.info("API shut down.")

    return app
