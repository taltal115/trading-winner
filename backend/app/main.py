"""FastAPI application entry point.

Controllers are thin: validate input, call a service, return the response.
No business logic, no Firestore access here (CODING_STANDARDS.md 2.3 / 4).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import ai, backtests, health, pipeline, portfolio, signals, trading
from app.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Trading System",
        version="0.1.0",
        description=f"Phase {int(settings.phase)} — {settings.environment}",
    )
    app.include_router(health.router)
    app.include_router(signals.router)
    app.include_router(pipeline.router)
    app.include_router(backtests.router)
    app.include_router(ai.router)
    app.include_router(portfolio.router)
    app.include_router(trading.router)
    return app


app = create_app()
