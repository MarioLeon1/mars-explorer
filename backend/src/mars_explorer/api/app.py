"""FastAPI application factory.

Run: ``uv run uvicorn mars_explorer.api.app:app --reload --port 8000`` (inside ``backend/``).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mars_explorer import __version__
from mars_explorer.api.routers import images, ingest, meta, rover, system, vision
from mars_explorer.core.config import Settings, get_settings
from mars_explorer.core.errors import AppError
from mars_explorer.core.logging import configure_logging
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.downloader import ImageDownloader
from mars_explorer.ingest.http import make_http_client
from mars_explorer.ingest.jobs import JobManager
from mars_explorer.vision.service import VisionService

log = logging.getLogger(__name__)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(
    settings: Settings | None = None, transport: httpx.BaseTransport | None = None
) -> FastAPI:
    """Build the app. ``transport`` lets tests replace all outbound HTTP (NASA downloads)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        app.state.settings = settings
        app.state.engine = make_engine(settings.database_path)
        app.state.http = make_http_client(settings, transport=transport)
        app.state.downloader = ImageDownloader(app.state.http, settings)
        app.state.jobs = JobManager(app.state.engine, settings, transport=transport)
        app.state.vision = VisionService(app.state.engine, settings, app.state.downloader)
        log.info("Mars Explorer API %s — data dir %s", __version__, settings.data_dir)
        yield
        app.state.jobs.shutdown()
        app.state.http.close()
        app.state.engine.dispose()

    app = FastAPI(
        title="Mars Explorer API",
        version=__version__,
        description="Real NASA Mars 2020 Perseverance data, served for the Mars Explorer UI.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []))
        return _error(422, "invalid_request", f"{where}: {first.get('msg', 'invalid request')}")

    for router in (
        meta.router,
        images.router,
        ingest.router,
        rover.router,
        system.router,
        vision.router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
