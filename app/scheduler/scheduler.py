"""APScheduler setup with a MongoDB-backed jobstore.

The scheduler persists its jobs in MongoDB, so registered schedules survive
process restarts. A single AsyncIOScheduler instance is shared per process.
"""

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler(settings: Settings) -> AsyncIOScheduler:
    """Create and start the shared scheduler. Idempotent within a process."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    jobstore = MongoDBJobStore(
        database=settings.mongodb_db,
        collection=settings.scheduler_jobs_collection,
        host=settings.mongodb_uri,
    )
    scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_jobstore(jobstore, alias="default")
    scheduler.start()
    _scheduler = scheduler
    logger.info("APScheduler started (timezone=%s)", settings.scheduler_timezone)
    return scheduler


def get_scheduler() -> AsyncIOScheduler:
    """Return the running scheduler or raise if not started."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not started")
    return _scheduler


def shutdown_scheduler(wait: bool = True) -> None:
    """Stop the scheduler. By default waits for in-flight jobs to finish
    (graceful shutdown) so a deploy/restart does not drop running work."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=wait)
        _scheduler = None
        logger.info("APScheduler stopped (graceful=%s)", wait)
