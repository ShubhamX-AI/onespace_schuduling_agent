# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Business logic for schedules: persistence + APScheduler job sync.

Each Schedule document maps 1:1 to an APScheduler job whose id equals the
document id. Mutations keep the two in sync.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from beanie import PydanticObjectId
from bson.errors import InvalidId

from src.api.models.schedule import ScheduleCreate, ScheduleUpdate
from src.core.db.db_schema import Schedule, ScheduleRun, ScheduleStatus, TriggerType
from src.core.exceptions import ConflictError, NotFoundError, ValidationError
from src.scheduling.jobs import execute_schedule
from src.scheduling.scheduler import get_scheduler

_TRIGGER_BUILDERS = {
    TriggerType.DATE: DateTrigger,
    TriggerType.INTERVAL: IntervalTrigger,
    TriggerType.CRON: CronTrigger,
}
# DateTrigger fires once and has no active window.
_WINDOWED_TRIGGERS = {TriggerType.INTERVAL, TriggerType.CRON}


def _resolve_timezone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError(f"Unknown timezone '{timezone}'") from exc


def build_trigger(
    trigger_type: TriggerType,
    trigger_args: dict[str, Any],
    timezone: str = "UTC",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Construct a timezone-aware APScheduler trigger.

    Raises ValidationError on a bad timezone or trigger args. The timezone makes
    firing independent of the host server's local clock.
    """
    if start_date and end_date and start_date >= end_date:
        raise ValidationError("start_date must be before end_date")
    tz = _resolve_timezone(timezone)
    args: dict[str, Any] = {**trigger_args, "timezone": tz}
    if trigger_type in _WINDOWED_TRIGGERS:
        args["start_date"] = start_date
        args["end_date"] = end_date
    try:
        return _TRIGGER_BUILDERS[trigger_type](**args)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid trigger_args for {trigger_type}: {exc}") from exc


def _trigger_for(schedule: Schedule):
    return build_trigger(
        schedule.trigger_type,
        schedule.trigger_args,
        schedule.timezone,
        schedule.start_date,
        schedule.end_date,
    )


def _register_job(schedule: Schedule) -> None:
    """Add or replace the APScheduler job for a schedule."""
    get_scheduler().add_job(
        execute_schedule,
        trigger=_trigger_for(schedule),
        id=str(schedule.id),
        kwargs={"schedule_id": str(schedule.id)},
        replace_existing=True,
    )


def _safe_remove_job(schedule_id: str) -> None:
    """Remove a job, ignoring the case where it does not exist."""
    try:
        get_scheduler().remove_job(schedule_id)
    except JobLookupError:
        pass


def next_run_at(schedule_id: str) -> datetime | None:
    """Live next-fire time from the scheduler, or None if no active job."""
    try:
        scheduler = get_scheduler()
    except RuntimeError:
        return None
    job = scheduler.get_job(schedule_id)
    return job.next_run_time if job else None


async def create_schedule(data: ScheduleCreate, owner_id: str) -> Schedule:
    if await _find_by_name(owner_id, data.name) is not None:
        raise ConflictError(f"Schedule '{data.name}' already exists")

    schedule = Schedule(**data.model_dump(), owner_id=owner_id)
    # Validate trigger (incl. timezone) before persisting.
    _trigger_for(schedule)
    await schedule.insert()
    # Keep DB and scheduler consistent: drop the document if job registration fails.
    if schedule.status == ScheduleStatus.ACTIVE:
        try:
            _register_job(schedule)
        except Exception:
            await schedule.delete()
            raise
    return schedule


async def list_schedules(owner_id: str) -> list[Schedule]:
    return await Schedule.find(Schedule.owner_id == owner_id).to_list()


async def list_runs(schedule_id: str, owner_id: str, limit: int) -> list[ScheduleRun]:
    """Most recent runs for a schedule, newest first."""
    schedule = await get_schedule(schedule_id, owner_id)  # 404 if not the caller's
    return (
        await ScheduleRun.find(ScheduleRun.schedule_id == schedule.id)
        .sort(-ScheduleRun.finished_at)
        .limit(limit)
        .to_list()
    )


def _object_id(schedule_id: str) -> PydanticObjectId:
    """Parse a path id; a malformed id is treated as 'not found' (404)."""
    try:
        return PydanticObjectId(schedule_id)
    except (InvalidId, ValueError):
        raise NotFoundError(f"Schedule '{schedule_id}' not found") from None


async def _find_by_name(owner_id: str, name: str) -> Schedule | None:
    return await Schedule.find_one(Schedule.owner_id == owner_id, Schedule.name == name)


async def get_schedule(schedule_id: str, owner_id: str) -> Schedule:
    """Fetch a schedule by id, scoped to its owner. Another owner's id is a 404."""
    schedule = await Schedule.get(_object_id(schedule_id))
    if schedule is None or schedule.owner_id != owner_id:
        raise NotFoundError(f"Schedule '{schedule_id}' not found")
    return schedule


async def update_schedule(schedule_id: str, data: ScheduleUpdate, owner_id: str) -> Schedule:
    schedule = await get_schedule(schedule_id, owner_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise ValidationError("No fields to update")

    new_name = changes.get("name")
    renaming = new_name is not None and new_name != schedule.name
    if renaming and await _find_by_name(owner_id, new_name) is not None:
        raise ConflictError(f"Schedule '{new_name}' already exists")

    for field, value in changes.items():
        setattr(schedule, field, value)
    _trigger_for(schedule)

    # Sync the scheduler before persisting so a scheduler failure leaves the DB
    # unchanged (the in-memory mutations above are discarded on raise).
    if schedule.status == ScheduleStatus.ACTIVE:
        _register_job(schedule)
    else:
        _safe_remove_job(str(schedule.id))

    schedule.touch()
    await schedule.save()
    return schedule


async def delete_schedule(schedule_id: str, owner_id: str) -> None:
    schedule = await get_schedule(schedule_id, owner_id)
    _safe_remove_job(str(schedule.id))
    await schedule.delete()


async def pause_schedule(schedule_id: str, owner_id: str) -> Schedule:
    """Stop a schedule from firing without deleting it."""
    schedule = await get_schedule(schedule_id, owner_id)
    if schedule.status != ScheduleStatus.PAUSED:
        _safe_remove_job(str(schedule.id))
        schedule.status = ScheduleStatus.PAUSED
        schedule.touch()
        await schedule.save()
    return schedule


async def resume_schedule(schedule_id: str, owner_id: str) -> Schedule:
    """Re-arm a paused schedule."""
    schedule = await get_schedule(schedule_id, owner_id)
    if schedule.status != ScheduleStatus.ACTIVE:
        schedule.status = ScheduleStatus.ACTIVE
        _register_job(schedule)
        schedule.touch()
        await schedule.save()
    return schedule


async def run_schedule_now(schedule_id: str, owner_id: str) -> Schedule:
    """Fire the job once immediately, independent of its trigger."""
    schedule = await get_schedule(schedule_id, owner_id)
    await execute_schedule(str(schedule.id))
    return schedule
