# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the schedule service: ownership scoping and control operations."""

import pytest

from src.core.db.db_schema import Schedule, ScheduleStatus
from src.core.exceptions import NotFoundError
from src.scheduling import lifecycle, schedule_service
from tests.factories import build_schedule


def _stub_get(monkeypatch: pytest.MonkeyPatch, *docs: Schedule) -> None:
    """``Schedule.get`` returns each doc in turn (the last one repeats)."""
    queue = list(docs)

    async def _get(_id):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(Schedule, "get", _get)


def _record_apply(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    async def _apply(schedule, changes):
        calls.append(changes)

    monkeypatch.setattr(lifecycle, "apply", _apply)
    return calls


async def test_other_owners_schedule_is_not_found(monkeypatch) -> None:
    schedule = build_schedule(owner_id="someone-else")
    _stub_get(monkeypatch, schedule)

    with pytest.raises(NotFoundError):
        await schedule_service.get_schedule(str(schedule.id), "test-owner")


async def test_pause_of_paused_schedule_is_a_no_op(monkeypatch) -> None:
    schedule = build_schedule(status=ScheduleStatus.PAUSED)
    _stub_get(monkeypatch, schedule)
    calls = _record_apply(monkeypatch)

    await schedule_service.pause_schedule(str(schedule.id), "test-owner")

    assert calls == []


async def test_resume_goes_through_lifecycle(monkeypatch) -> None:
    schedule = build_schedule(status=ScheduleStatus.PAUSED)
    _stub_get(monkeypatch, schedule)
    calls = _record_apply(monkeypatch)

    await schedule_service.resume_schedule(str(schedule.id), "test-owner")

    assert calls == [{"status": ScheduleStatus.ACTIVE}]


async def test_run_now_queues_a_one_off_job(monkeypatch, live_scheduler) -> None:
    """Returns without running the action; the job fires it immediately."""
    schedule = build_schedule(status=ScheduleStatus.PAUSED)
    _stub_get(monkeypatch, schedule)

    result = await schedule_service.run_schedule_now(str(schedule.id), "test-owner")
    await schedule_service.run_schedule_now(str(schedule.id), "test-owner")  # collapses

    assert result is schedule
    (job,) = live_scheduler.get_jobs()
    assert job.id == f"run-now:{schedule.id}"
    assert job.kwargs == {"schedule_id": str(schedule.id)}
