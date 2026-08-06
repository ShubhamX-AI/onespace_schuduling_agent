# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""FastAPI application factory and lifecycle wiring."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.routes import health
from src.api.routes.v1.router import api_router
from src.core.config import Settings, get_settings
from src.core.db.db_connect import close_mongo_connection, connect_to_mongo
from src.core.exceptions import register_exception_handlers
from src.core.logging.logger import configure_logging, get_logger
from src.scheduling.scheduler import shutdown_scheduler, start_scheduler

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    await connect_to_mongo(settings)
    start_scheduler(settings)
    logger.info("%s startup complete", settings.app_name)
    try:
        yield
    finally:
        shutdown_scheduler()
        await close_mongo_connection()
        logger.info("%s shutdown complete", settings.app_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(health.router)  # unprefixed: a probe, not part of the API
    _mount_documentation(app, settings)
    return app


def _mount_documentation(app: FastAPI, settings: Settings) -> None:
    """Serve the built MkDocs site at /documentation, if it has been built."""
    site = Path(settings.docs_site_dir)
    if not site.is_dir():
        logger.info("Docs site %s not found; /documentation not mounted", site)
        return
    app.mount("/documentation", StaticFiles(directory=site, html=True), name="documentation")


app = create_app()
