# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Schedule CRUD + control endpoints. All responses use the standard envelope."""

from fastapi import APIRouter, Depends, Query

from src.api.models.response_schemas import ApiResponse
from src.api.models.schedule import (
    ScheduleCreate,
    ScheduleRead,
    ScheduleRunRead,
    ScheduleUpdate,
    ValidateTriggerRequest,
)
from src.api.routes.v1._common import current_owner
from src.core.db.db_schema import Schedule
from src.core.exceptions import ValidationError
from src.scheduling import lifecycle, schedule_service
from src.scheduling.triggers import build_trigger

router = APIRouter()


def _read(schedule: Schedule) -> ScheduleRead:
    """Serialize a schedule, enriching it with the live next-run time."""
    return ScheduleRead.from_document(schedule, next_run_at=lifecycle.next_run_at(str(schedule.id)))


@router.post("", response_model=ApiResponse[ScheduleRead], status_code=201)
async def create_schedule(
    data: ScheduleCreate, owner_id: str = Depends(current_owner)
) -> ApiResponse[ScheduleRead]:
    schedule = await schedule_service.create_schedule(data.model_dump(), owner_id)
    return ApiResponse.ok(_read(schedule), "Schedule created")


@router.post("/validate", response_model=ApiResponse[None])
async def validate_trigger(data: ValidateTriggerRequest) -> ApiResponse[None]:
    """Check a trigger spec (incl. timezone) without persisting anything."""
    try:
        build_trigger(
            data.trigger_type, data.trigger_args, data.timezone, data.start_date, data.end_date
        )
    except ValidationError as exc:
        return ApiResponse(success=False, message=exc.message)
    return ApiResponse.ok(message="Trigger is valid")


@router.get("", response_model=ApiResponse[list[ScheduleRead]])
async def list_schedules(owner_id: str = Depends(current_owner)) -> ApiResponse[list[ScheduleRead]]:
    schedules = await schedule_service.list_schedules(owner_id)
    return ApiResponse.ok([_read(s) for s in schedules], "Schedules retrieved")


@router.get("/{schedule_id}", response_model=ApiResponse[ScheduleRead])
async def get_schedule(
    schedule_id: str, owner_id: str = Depends(current_owner)
) -> ApiResponse[ScheduleRead]:
    schedule = await schedule_service.get_schedule(schedule_id, owner_id)
    return ApiResponse.ok(_read(schedule), "Schedule retrieved")


@router.get("/{schedule_id}/runs", response_model=ApiResponse[list[ScheduleRunRead]])
async def list_runs(
    schedule_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    owner_id: str = Depends(current_owner),
) -> ApiResponse[list[ScheduleRunRead]]:
    """Recent run outcomes for a schedule, newest first."""
    runs = await schedule_service.list_runs(schedule_id, owner_id, limit)
    return ApiResponse.ok([ScheduleRunRead.from_document(r) for r in runs], "Runs retrieved")


@router.patch("/{schedule_id}", response_model=ApiResponse[ScheduleRead])
async def update_schedule(
    schedule_id: str, data: ScheduleUpdate, owner_id: str = Depends(current_owner)
) -> ApiResponse[ScheduleRead]:
    schedule = await schedule_service.update_schedule(
        schedule_id, data.model_dump(exclude_unset=True), owner_id
    )
    return ApiResponse.ok(_read(schedule), "Schedule updated")


@router.delete("/{schedule_id}", response_model=ApiResponse[None])
async def delete_schedule(
    schedule_id: str, owner_id: str = Depends(current_owner)
) -> ApiResponse[None]:
    await schedule_service.delete_schedule(schedule_id, owner_id)
    return ApiResponse.ok(message="Schedule deleted")


@router.post("/{schedule_id}/pause", response_model=ApiResponse[ScheduleRead])
async def pause_schedule(
    schedule_id: str, owner_id: str = Depends(current_owner)
) -> ApiResponse[ScheduleRead]:
    schedule = await schedule_service.pause_schedule(schedule_id, owner_id)
    return ApiResponse.ok(_read(schedule), "Schedule paused")


@router.post("/{schedule_id}/resume", response_model=ApiResponse[ScheduleRead])
async def resume_schedule(
    schedule_id: str, owner_id: str = Depends(current_owner)
) -> ApiResponse[ScheduleRead]:
    schedule = await schedule_service.resume_schedule(schedule_id, owner_id)
    return ApiResponse.ok(_read(schedule), "Schedule resumed")


@router.post("/{schedule_id}/run", response_model=ApiResponse[ScheduleRead], status_code=202)
async def run_schedule_now(
    schedule_id: str, owner_id: str = Depends(current_owner)
) -> ApiResponse[ScheduleRead]:
    """Queue one immediate fire, independent of its schedule. Poll /runs for the outcome."""
    schedule = await schedule_service.run_schedule_now(schedule_id, owner_id)
    return ApiResponse.ok(_read(schedule), "Schedule run queued")
