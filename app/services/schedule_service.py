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

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.schedule import Schedule, ScheduleRun, ScheduleStatus, TriggerType
from app.scheduler.jobs import execute_schedule
from app.scheduler.scheduler import get_scheduler
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate

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


async def create_schedule(data: ScheduleCreate) -> Schedule:
    if await Schedule.find_one(Schedule.name == data.name) is not None:
        raise ConflictError(f"Schedule '{data.name}' already exists")

    schedule = Schedule(**data.model_dump())
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


async def list_schedules() -> list[Schedule]:
    return await Schedule.find_all().to_list()


async def list_runs(schedule_id: str, limit: int) -> list[ScheduleRun]:
    """Most recent runs for a schedule, newest first."""
    object_id = _object_id(schedule_id)
    return (
        await ScheduleRun.find(ScheduleRun.schedule_id == object_id)
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


async def get_schedule(schedule_id: str) -> Schedule:
    schedule = await Schedule.get(_object_id(schedule_id))
    if schedule is None:
        raise NotFoundError(f"Schedule '{schedule_id}' not found")
    return schedule


async def update_schedule(schedule_id: str, data: ScheduleUpdate) -> Schedule:
    schedule = await get_schedule(schedule_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise ValidationError("No fields to update")

    new_name = changes.get("name")
    if new_name is not None and new_name != schedule.name:
        if await Schedule.find_one(Schedule.name == new_name) is not None:
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


async def delete_schedule(schedule_id: str) -> None:
    schedule = await get_schedule(schedule_id)
    _safe_remove_job(str(schedule.id))
    await schedule.delete()


async def pause_schedule(schedule_id: str) -> Schedule:
    """Stop a schedule from firing without deleting it."""
    schedule = await get_schedule(schedule_id)
    if schedule.status != ScheduleStatus.PAUSED:
        _safe_remove_job(str(schedule.id))
        schedule.status = ScheduleStatus.PAUSED
        schedule.touch()
        await schedule.save()
    return schedule


async def resume_schedule(schedule_id: str) -> Schedule:
    """Re-arm a paused schedule."""
    schedule = await get_schedule(schedule_id)
    if schedule.status != ScheduleStatus.ACTIVE:
        schedule.status = ScheduleStatus.ACTIVE
        _register_job(schedule)
        schedule.touch()
        await schedule.save()
    return schedule


async def run_schedule_now(schedule_id: str) -> Schedule:
    """Fire the job once immediately, independent of its trigger."""
    schedule = await get_schedule(schedule_id)
    await execute_schedule(str(schedule.id))
    return schedule
