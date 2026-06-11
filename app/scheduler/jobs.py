"""Job callables fired by APScheduler.

Executors must be module-level functions (importable by reference) so the
MongoDB jobstore can serialize them. ``execute_schedule`` is async so it can
record its own run outcome to MongoDB via Beanie; AsyncIOScheduler awaits it.

The actual work is a stub (logs the firing) — real execution logic is a future
task. The surrounding success/error bookkeeping is the part worth keeping.
"""

from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId

from app.core.logging import get_logger
from app.models.schedule import RunStatus, Schedule

logger = get_logger(__name__)


async def _do_work(schedule_id: str, payload: dict[str, Any]) -> None:
    """Stub work performed when a schedule fires. Replace with real logic."""
    logger.info("Schedule %s fired with payload=%s", schedule_id, payload)


async def execute_schedule(schedule_id: str, payload: dict[str, Any]) -> None:
    """Run a schedule's work and record the outcome on its document."""
    status = RunStatus.SUCCESS
    error: str | None = None
    try:
        await _do_work(schedule_id, payload)
    except Exception as exc:  # record failure, don't crash the scheduler
        status = RunStatus.ERROR
        error = str(exc)
        logger.exception("Schedule %s failed", schedule_id)
    finally:
        await _record_run(schedule_id, status, error)


async def _record_run(schedule_id: str, status: RunStatus, error: str | None) -> None:
    schedule = await Schedule.get(PydanticObjectId(schedule_id))
    if schedule is None:
        return
    schedule.last_run_at = datetime.now(UTC)
    schedule.last_status = status
    schedule.last_error = error
    await schedule.save()
