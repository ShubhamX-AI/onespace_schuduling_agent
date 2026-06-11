"""Job callables fired by APScheduler.

Executors must be module-level functions (importable by reference) so the
MongoDB jobstore can serialize them. ``execute_schedule`` is async so it can
record its own run outcome to MongoDB via Beanie; AsyncIOScheduler awaits it.

The job receives only the schedule id and reloads the document on each fire, so
the action and payload are always read fresh from MongoDB (the source of truth)
rather than from stale jobstore kwargs. Each fire writes a ScheduleRun record,
updates the schedule's last-run summary, and fires the notify callback.
"""

from datetime import UTC, datetime

from beanie import PydanticObjectId
from bson.errors import InvalidId

from app.core.logging import get_logger
from app.models.schedule import RunStatus, Schedule, ScheduleRun
from app.scheduler.actions import WebhookError, notify, run_action

logger = get_logger(__name__)


async def execute_schedule(schedule_id: str) -> None:
    """Run a schedule's action, record the run, and notify the creator."""
    try:
        object_id = PydanticObjectId(schedule_id)
    except (InvalidId, ValueError):
        logger.warning("Schedule fired with malformed id %r; skipping", schedule_id)
        return
    schedule = await Schedule.get(object_id)
    if schedule is None:
        logger.warning("Schedule %s fired but no longer exists", schedule_id)
        return

    started_at = datetime.now(UTC)
    status = RunStatus.SUCCESS
    error: str | None = None
    http_status: int | None = None
    response_body: str | None = None
    try:
        result = await run_action(schedule)
        http_status, response_body = result.http_status, result.body
    except WebhookError as exc:
        status, error = RunStatus.ERROR, str(exc)
        http_status, response_body = exc.http_status, exc.body
        logger.exception("Schedule %s failed", schedule_id)
    except Exception as exc:  # never crash the scheduler
        status, error = RunStatus.ERROR, str(exc)
        logger.exception("Schedule %s failed", schedule_id)

    run = ScheduleRun(
        schedule_id=schedule.id,
        status=status,
        http_status=http_status,
        response_body=response_body,
        error=error,
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )
    run.notified = await notify(schedule, run)
    await run.insert()

    schedule.last_run_at = run.finished_at
    schedule.last_status = status
    schedule.last_error = error
    schedule.last_http_status = http_status
    await schedule.save()
