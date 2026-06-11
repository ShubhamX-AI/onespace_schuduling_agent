"""FastAPI application factory and lifecycle wiring."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.mongodb import close_mongo_connection, connect_to_mongo
from app.scheduler import shutdown_scheduler, start_scheduler

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
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
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
