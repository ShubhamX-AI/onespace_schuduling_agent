# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Schedule lifecycle: every status transition and the APScheduler job behind it.

Each Schedule document maps 1:1 to an APScheduler job whose id equals the
document id. This is the only module that arms or disarms jobs, so the DB and
the scheduler are kept in sync in one place.

When a step fails, the schedule ends in the state that does not fire:

- disarm, then save: a failed save leaves the document active with no job,
  which the startup ``resync_jobs`` repairs;
- save, then arm: a failed arm reverts the DB change and re-raises.

Writes are partial (``$set``/``$inc``), never a full-document save, so a run
finishing during an edit and an edit made during a run do not overwrite each
other.
"""

from datetime import UTC, datetime
from typing import Any

from apscheduler.jobstores.base import JobLookupError
from beanie import PydanticObjectId

from src.core.config import get_settings
from src.core.db.db_schema import Schedule, ScheduleStatus
from src.core.exceptions import ValidationError
from src.core.logging.logger import get_logger
from src.scheduling.scheduler import get_scheduler
from src.scheduling.triggers import TRIGGER_FIELDS, trigger_for

logger = get_logger(__name__)

# A text reference, not the function: jobs imports this module, and the MongoDB
# jobstore stores this same string for every job anyway.
_EXECUTOR = "src.scheduling.jobs:execute_schedule"


def _has_future_fire(trigger, now: datetime) -> bool:
    next_fire = trigger.get_next_fire_time(None, now)
    return next_fire is not None and next_fire >= now


def _armable_trigger(schedule: Schedule):
    """The schedule's trigger, or ValidationError when it would never fire again
    (e.g. a one-shot whose date has passed): arming it would only misfire."""
    trigger = trigger_for(schedule)
    if not _has_future_fire(trigger, datetime.now(UTC)):
        raise ValidationError("Schedule has no future fire")
    return trigger


def _arm(schedule: Schedule, trigger) -> None:
    """Add or replace the APScheduler job for a schedule."""
    get_scheduler().add_job(
        _EXECUTOR,
        trigger=trigger,
        id=str(schedule.id),
        kwargs={"schedule_id": str(schedule.id)},
        replace_existing=True,
    )


def _disarm(job_id: str) -> None:
    try:
        get_scheduler().remove_job(job_id)
    except JobLookupError:
        pass


async def create(schedule: Schedule) -> None:
    """Insert a new schedule and arm it if active. Nothing is kept on failure."""
    active = schedule.status == ScheduleStatus.ACTIVE
    # validate before persisting
    trigger = _armable_trigger(schedule) if active else trigger_for(schedule)
    await schedule.insert()
    if active:
        try:
            _arm(schedule, trigger)
        except Exception:
            await schedule.delete()
            raise


async def apply(schedule: Schedule, changes: dict[str, Any]) -> None:
    """Apply field edits (``status`` included) and keep the job in sync.

    Moving to active resets ``consecutive_errors``, so a resumed schedule is not
    auto-paused again by its next single failure.
    """
    changes = {**changes, "updated_at": datetime.now(UTC)}
    resuming = (
        changes.get("status") == ScheduleStatus.ACTIVE and schedule.status != ScheduleStatus.ACTIVE
    )
    if resuming:
        changes["consecutive_errors"] = 0
    active = changes.get("status", schedule.status) == ScheduleStatus.ACTIVE
    trigger_changed = bool(changes.keys() & TRIGGER_FIELDS)

    # Validate before any write. Pausing alone must not fail on a stored trigger.
    if not active:
        if trigger_changed:
            trigger_for(schedule.model_copy(update=changes))
        _disarm(str(schedule.id))
        await schedule.set(changes)
        return

    if not (resuming or trigger_changed):
        # Nothing the job depends on changed: re-arming would restart an
        # interval from now and shift its next fire.
        await schedule.set(changes)
        return

    trigger = _armable_trigger(schedule.model_copy(update=changes))
    before = {field: getattr(schedule, field) for field in changes}
    await schedule.set(changes)
    try:
        _arm(schedule, trigger)
    except Exception:
        await schedule.set(before)
        raise


def run_now(schedule: Schedule) -> None:
    """Queue one immediate fire, independent of the trigger and of ``status``.

    A separate one-off job (not the trigger job), stored in the jobstore so it
    survives a restart; repeat calls before it fires collapse into one.
    ponytail: may overlap a scheduled fire of the same schedule (max_instances
    counts per job id); add a per-schedule lock in execute_schedule if that matters.
    """
    get_scheduler().add_job(
        _EXECUTOR,
        id=f"run-now:{schedule.id}",
        kwargs={"schedule_id": str(schedule.id)},
        replace_existing=True,
        misfire_grace_time=None,  # fire however late the scheduler gets to it
    )


async def delete(schedule: Schedule) -> None:
    _disarm(str(schedule.id))
    await schedule.delete()


async def pause_if_failing(schedule_id: PydanticObjectId) -> None:
    """Pause an active schedule once it reaches the consecutive-error threshold.

    The DB decides atomically (only an active schedule at the threshold
    matches), so a schedule paused or resumed during the run is left alone.
    ponytail: DB first, then disarm. If disarm raises, the job keeps firing
    while paused until the next resume or restart; APScheduler logs the error.
    """
    threshold = get_settings().consecutive_error_threshold
    result = await Schedule.find_one(
        Schedule.id == schedule_id,
        Schedule.status == ScheduleStatus.ACTIVE,
        Schedule.consecutive_errors >= threshold,
    ).update({"$set": {"status": ScheduleStatus.PAUSED, "updated_at": datetime.now(UTC)}})
    if result.modified_count:
        _disarm(str(schedule_id))
        logger.info("Schedule %s paused after %d consecutive errors", schedule_id, threshold)


async def resync_jobs() -> dict[str, int]:
    """Re-arm active schedules that have no APScheduler job. Idempotent.

    The jobstore deletes any job it cannot restore — a stored job holds a
    textual reference to its function, so moving the module (app/ -> src/)
    orphaned every existing job. The Schedule documents are the source of
    truth, so rebuild the missing jobs from them on startup.
    """
    scheduler = get_scheduler()
    now = datetime.now(UTC)
    restored = skipped = failed = 0

    for schedule in await Schedule.find(Schedule.status == ScheduleStatus.ACTIVE).to_list():
        try:
            if scheduler.get_job(str(schedule.id)) is not None:
                skipped += 1
            elif _has_future_fire(trigger := trigger_for(schedule), now):
                _arm(schedule, trigger)
                restored += 1
            else:
                # Nothing left to fire (one-shot already past, or end_date
                # expired) — re-arming it would fire it again as a misfire.
                skipped += 1
        except Exception:
            failed += 1
            logger.exception("Could not restore schedule %s", schedule.id)

    logger.info("Scheduler resync: restored=%d skipped=%d failed=%d", restored, skipped, failed)
    return {"restored": restored, "skipped": skipped, "failed": failed}


def next_run_at(schedule_id: str) -> datetime | None:
    """Live next-fire time from the scheduler, or None if no active job."""
    try:
        scheduler = get_scheduler()
    except RuntimeError:
        return None
    job = scheduler.get_job(schedule_id)
    return job.next_run_time if job else None
