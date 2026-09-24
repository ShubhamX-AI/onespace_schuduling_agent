# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
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

from src.core.config import get_settings
from src.core.db.db_schema import RunStatus, Schedule, ScheduleRun, ScheduleStatus
from src.core.logging.logger import get_logger
from src.scheduling.actions import WebhookError, notify, run_action
from src.scheduling.scheduler import remove_job_if_exists

logger = get_logger(__name__)


async def execute_schedule(schedule_id: str) -> None:
    """Run a schedule's action, record the run, and notify the creator."""
    schedule = await _load_schedule(schedule_id)
    if schedule is None:
        return

    run = await _run_action(schedule)
    run.notified = await notify(schedule, run)
    await run.insert()

    _record_outcome(schedule, run)
    _pause_if_failing(schedule)
    await schedule.save()


async def _load_schedule(schedule_id: str) -> Schedule | None:
    try:
        object_id = PydanticObjectId(schedule_id)
    except (InvalidId, ValueError):
        logger.warning("Schedule fired with malformed id %r; skipping", schedule_id)
        return None
    schedule = await Schedule.get(object_id)
    if schedule is None:
        logger.warning("Schedule %s fired but no longer exists", schedule_id)
    return schedule


async def _run_action(schedule: Schedule) -> ScheduleRun:
    """Fire the action and capture its outcome. Never raises."""
    run = ScheduleRun(
        schedule_id=schedule.id,
        status=RunStatus.SUCCESS,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    try:
        result = await run_action(schedule)
        run.http_status, run.response_body = result.http_status, result.body
    except WebhookError as exc:
        run.status, run.error = RunStatus.ERROR, str(exc)
        run.http_status, run.response_body = exc.http_status, exc.body
        logger.exception("Schedule %s failed", schedule.id)
    except Exception as exc:  # never crash the scheduler
        run.status, run.error = RunStatus.ERROR, str(exc)
        logger.exception("Schedule %s failed", schedule.id)
    run.finished_at = datetime.now(UTC)
    return run


def _record_outcome(schedule: Schedule, run: ScheduleRun) -> None:
    succeeded = run.status == RunStatus.SUCCESS
    schedule.consecutive_errors = 0 if succeeded else schedule.consecutive_errors + 1
    schedule.last_run_at = run.finished_at
    schedule.last_status = run.status
    schedule.last_error = run.error
    schedule.last_http_status = run.http_status


def _pause_if_failing(schedule: Schedule) -> None:
    """Auto-pause a schedule once it hits the consecutive-error threshold."""
    threshold = get_settings().consecutive_error_threshold
    if schedule.consecutive_errors < threshold:
        return
    schedule.status = ScheduleStatus.PAUSED
    remove_job_if_exists(str(schedule.id))
    logger.info(
        "Schedule %s paused after %d consecutive errors (threshold: %d)",
        schedule.id,
        schedule.consecutive_errors,
        threshold,
    )
