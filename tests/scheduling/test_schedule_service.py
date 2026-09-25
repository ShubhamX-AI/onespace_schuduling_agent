# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the schedule service: ownership scoping and control operations."""

import pytest

from src.core.db.db_schema import MASKED_VALUE, Schedule, ScheduleStatus
from src.core.exceptions import NotFoundError, ValidationError
from src.scheduling import lifecycle, schedule_service
from tests.factories import build_schedule, build_schedule_create, build_webhook_action


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


# --- masked header values (reads return MASKED_VALUE; writes must not store it) ---


def _stored(headers: dict[str, str]) -> Schedule:
    return build_schedule(action=build_webhook_action(headers=headers))


def _action_with(headers: dict[str, str]) -> dict:
    return build_webhook_action(headers=headers).model_dump()


async def test_update_keeps_stored_value_for_masked_header(monkeypatch) -> None:
    schedule = _stored({"Authorization": "Bearer real"})
    _stub_get(monkeypatch, schedule)
    calls = _record_apply(monkeypatch)

    changes = {"action": _action_with({"authorization": MASKED_VALUE, "X-New": "v"})}
    await schedule_service.update_schedule(str(schedule.id), changes, "test-owner")

    assert calls[0]["action"]["headers"] == {"authorization": "Bearer real", "X-New": "v"}


async def test_update_replaces_header_sent_with_real_value(monkeypatch) -> None:
    schedule = _stored({"Authorization": "Bearer old"})
    _stub_get(monkeypatch, schedule)
    calls = _record_apply(monkeypatch)

    changes = {"action": _action_with({"Authorization": "Bearer new"})}
    await schedule_service.update_schedule(str(schedule.id), changes, "test-owner")

    assert calls[0]["action"]["headers"] == {"Authorization": "Bearer new"}


async def test_update_rejects_masked_header_without_stored_value(monkeypatch) -> None:
    schedule = _stored({})
    _stub_get(monkeypatch, schedule)
    calls = _record_apply(monkeypatch)

    changes = {"action": _action_with({"Authorization": MASKED_VALUE})}
    with pytest.raises(ValidationError, match="Authorization"):
        await schedule_service.update_schedule(str(schedule.id), changes, "test-owner")
    assert calls == []  # nothing written


async def test_create_rejects_masked_header(monkeypatch) -> None:
    async def _no_match(*_args):
        return None

    monkeypatch.setattr(schedule_service, "_find_by_name", _no_match)
    fields = build_schedule_create(action=build_webhook_action(headers={"X-Key": MASKED_VALUE}))

    with pytest.raises(ValidationError, match="X-Key"):
        await schedule_service.create_schedule(fields.model_dump(), "test-owner")
