# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""The Run module: one fire of a schedule, from load to recorded outcome.

``execute_schedule`` is the executor APScheduler fires. It must stay a
module-level function at this path: the MongoDB jobstore stores it by reference.

The job receives only the schedule id and reloads the document on each fire, so
the action and payload are always read fresh from MongoDB (the source of truth)
rather than from stale jobstore kwargs. Each fire runs the action, writes the
schedule's run summary (auto-pausing via the lifecycle), notifies the creator,
and inserts a ScheduleRun record — in that order, so the error count is never
lost to a failure in a best-effort step.
"""

from datetime import UTC, datetime

from beanie import PydanticObjectId
from bson.errors import InvalidId

from src.core.db.db_schema import RunStatus, Schedule, ScheduleRun
from src.core.logging.logger import get_logger
from src.scheduling import lifecycle
from src.scheduling.actions import notify, run_action

logger = get_logger(__name__)


async def execute_schedule(schedule_id: str) -> None:
    """Run a schedule's action, record the outcome, and notify the creator."""
    schedule = await _load_schedule(schedule_id)
    if schedule is None:
        return

    started_at = datetime.now(UTC)
    result = await run_action(schedule)
    run = ScheduleRun(
        schedule_id=schedule.id,
        status=RunStatus.SUCCESS if result.error is None else RunStatus.ERROR,
        http_status=result.http_status,
        response_body=result.body,
        error=result.error,
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )

    await _record_summary(run)
    if run.status != RunStatus.SUCCESS:
        await lifecycle.pause_if_failing(schedule.id)

    run.notified = await notify(schedule, run)
    try:
        await run.insert()
    except Exception:  # history is best-effort; the summary above is already written
        logger.exception("Could not store run history for schedule %s", schedule.id)


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


async def _record_summary(run: ScheduleRun) -> None:
    """Write the run to the schedule's run summary.

    Touches only the run-summary fields, so edits made while the run was in
    flight survive.
    """
    summary = {
        "last_run_at": run.finished_at,
        "last_status": run.status,
        "last_error": run.error,
        "last_http_status": run.http_status,
    }
    if run.status == RunStatus.SUCCESS:
        update = {"$set": {**summary, "consecutive_errors": 0}}
    else:
        update = {"$set": summary, "$inc": {"consecutive_errors": 1}}
    await Schedule.find_one(Schedule.id == run.schedule_id).update(update)
