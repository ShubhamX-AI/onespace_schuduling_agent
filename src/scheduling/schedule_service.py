# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Business logic for schedules: ownership, name uniqueness, reads.

Every status change and its APScheduler job sync go through
``src.scheduling.lifecycle``.
"""

from typing import Any

from beanie import PydanticObjectId
from bson.errors import InvalidId

from src.core.db.db_schema import Schedule, ScheduleRun, ScheduleStatus
from src.core.exceptions import ConflictError, NotFoundError, ValidationError
from src.scheduling import lifecycle


async def create_schedule(fields: dict[str, Any], owner_id: str) -> Schedule:
    if await _find_by_name(owner_id, fields["name"]) is not None:
        raise ConflictError(f"Schedule '{fields['name']}' already exists")

    schedule = Schedule(**fields, owner_id=owner_id)
    await lifecycle.create(schedule)
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


async def update_schedule(schedule_id: str, changes: dict[str, Any], owner_id: str) -> Schedule:
    """Apply a partial edit; ``changes`` holds only the fields the caller set."""
    schedule = await get_schedule(schedule_id, owner_id)
    if not changes:
        raise ValidationError("No fields to update")

    new_name = changes.get("name")
    renaming = new_name is not None and new_name != schedule.name
    if renaming and await _find_by_name(owner_id, new_name) is not None:
        raise ConflictError(f"Schedule '{new_name}' already exists")

    await lifecycle.apply(schedule, changes)
    return schedule


async def delete_schedule(schedule_id: str, owner_id: str) -> None:
    schedule = await get_schedule(schedule_id, owner_id)
    await lifecycle.delete(schedule)


async def pause_schedule(schedule_id: str, owner_id: str) -> Schedule:
    """Stop a schedule from firing without deleting it."""
    schedule = await get_schedule(schedule_id, owner_id)
    if schedule.status != ScheduleStatus.PAUSED:
        await lifecycle.apply(schedule, {"status": ScheduleStatus.PAUSED})
    return schedule


async def resume_schedule(schedule_id: str, owner_id: str) -> Schedule:
    """Re-arm a paused schedule. Resets its consecutive-error count."""
    schedule = await get_schedule(schedule_id, owner_id)
    if schedule.status != ScheduleStatus.ACTIVE:
        await lifecycle.apply(schedule, {"status": ScheduleStatus.ACTIVE})
    return schedule


async def run_schedule_now(schedule_id: str, owner_id: str) -> Schedule:
    """Queue one immediate fire, independent of its trigger. Returns at once;
    the outcome lands in the run summary and run history when the job runs."""
    schedule = await get_schedule(schedule_id, owner_id)
    lifecycle.run_now(schedule)
    return schedule
