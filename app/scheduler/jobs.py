"""Job callables fired by APScheduler.

Executors must be module-level functions (importable by reference) so the
MongoDB jobstore can serialize them. ``execute_schedule`` is async so it can
record its own run outcome to MongoDB via Beanie; AsyncIOScheduler awaits it.

The job receives only the schedule id and reloads the document on each fire, so
the action and payload are always read fresh from MongoDB (the source of truth)
rather than from stale jobstore kwargs.
"""

from datetime import UTC, datetime

from beanie import PydanticObjectId

from app.core.logging import get_logger
from app.models.schedule import RunStatus, Schedule
from app.scheduler.actions import run_action

logger = get_logger(__name__)


async def execute_schedule(schedule_id: str) -> None:
    """Run a schedule's action and record the outcome on its document."""
    schedule = await Schedule.get(PydanticObjectId(schedule_id))
    if schedule is None:
        logger.warning("Schedule %s fired but no longer exists", schedule_id)
        return

    status = RunStatus.SUCCESS
    error: str | None = None
    try:
        await run_action(schedule)
    except Exception as exc:  # record failure, don't crash the scheduler
        status = RunStatus.ERROR
        error = str(exc)
        logger.exception("Schedule %s failed", schedule_id)

    schedule.last_run_at = datetime.now(UTC)
    schedule.last_status = status
    schedule.last_error = error
    await schedule.save()
