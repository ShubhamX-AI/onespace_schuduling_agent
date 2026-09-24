# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the schedule lifecycle: status transitions, auto-pause, resync.

A real scheduler on an in-memory jobstore (``live_scheduler``) shows which jobs
are armed. Beanie writes are faked and recorded, so tests assert the shape of
each update — atomic Mongo semantics are not exercised without a live MongoDB.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from src.core.db.db_schema import Schedule, ScheduleStatus, TriggerType
from src.core.exceptions import ValidationError
from src.scheduling import lifecycle
from src.scheduling.lifecycle import resync_jobs
from tests.factories import build_schedule

_EXECUTOR = "src.scheduling.jobs:execute_schedule"


@pytest.fixture
def sets(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Fake ``Schedule.set``: apply the fields locally and record each call."""
    calls: list[dict] = []

    async def _set(self, expression: dict) -> Schedule:
        calls.append(dict(expression))
        for field, value in expression.items():
            setattr(self, field, value)
        return self

    monkeypatch.setattr(Schedule, "set", _set)
    return calls


class _FakeUpdates:
    """Fake ``Schedule.find_one(...).update(...)``: records each update document and
    reports ``modified`` documents changed (the conditional auto-pause match)."""

    def __init__(self, modified: int = 1) -> None:
        self.modified = modified
        self.updates: list[dict] = []

    def find_one(self, *_filters):
        return self

    async def update(self, update: dict):
        self.updates.append(update)
        return SimpleNamespace(modified_count=self.modified)


@pytest.fixture
def updates(monkeypatch: pytest.MonkeyPatch) -> _FakeUpdates:
    fake = _FakeUpdates()
    monkeypatch.setattr(Schedule, "find_one", classmethod(lambda cls, *f: fake.find_one(*f)))
    return fake


def _arm(scheduler, schedule: Schedule) -> None:
    job_id = str(schedule.id)
    scheduler.add_job(_EXECUTOR, "interval", seconds=60, id=job_id, kwargs={"schedule_id": job_id})


# --- apply: pause / resume / edit -------------------------------------------


async def test_resume_arms_job_and_resets_error_count(live_scheduler, sets) -> None:
    """A schedule auto-paused at the threshold must not re-pause on its next failure."""
    schedule = build_schedule(status=ScheduleStatus.PAUSED, consecutive_errors=50)

    await lifecycle.apply(schedule, {"status": ScheduleStatus.ACTIVE})

    assert live_scheduler.get_job(str(schedule.id)) is not None
    assert sets[0]["consecutive_errors"] == 0
    assert schedule.status == ScheduleStatus.ACTIVE


async def test_edit_of_active_schedule_keeps_error_count(live_scheduler, sets) -> None:
    schedule = build_schedule(consecutive_errors=3)

    await lifecycle.apply(schedule, {"trigger_args": {"seconds": 30}})

    assert "consecutive_errors" not in sets[0]
    assert live_scheduler.get_job(str(schedule.id)).trigger.interval == timedelta(seconds=30)


async def test_pause_disarms_before_saving(live_scheduler, monkeypatch) -> None:
    """A failed save leaves no job firing (resync re-arms it on restart)."""
    schedule = build_schedule()
    _arm(live_scheduler, schedule)

    async def _failing_set(self, expression):
        raise RuntimeError("mongo down")

    monkeypatch.setattr(Schedule, "set", _failing_set)

    with pytest.raises(RuntimeError):
        await lifecycle.apply(schedule, {"status": ScheduleStatus.PAUSED})

    assert live_scheduler.get_job(str(schedule.id)) is None


async def test_pause_does_not_validate_stored_trigger(live_scheduler, sets) -> None:
    schedule = build_schedule(timezone="Mars/Phobos")

    await lifecycle.apply(schedule, {"status": ScheduleStatus.PAUSED})

    assert sets[0]["status"] == ScheduleStatus.PAUSED


async def test_invalid_edit_writes_nothing(live_scheduler, sets) -> None:
    schedule = build_schedule()

    with pytest.raises(ValidationError):
        await lifecycle.apply(schedule, {"timezone": "Mars/Phobos"})

    assert sets == []


async def test_failed_arm_reverts_the_saved_edit(live_scheduler, sets, monkeypatch) -> None:
    schedule = build_schedule(status=ScheduleStatus.PAUSED, consecutive_errors=50)

    def _boom(*args, **kwargs):
        raise RuntimeError("jobstore down")

    monkeypatch.setattr(live_scheduler, "add_job", _boom)

    with pytest.raises(RuntimeError):
        await lifecycle.apply(schedule, {"status": ScheduleStatus.ACTIVE})

    assert schedule.status == ScheduleStatus.PAUSED
    assert schedule.consecutive_errors == 50
    assert len(sets) == 2  # the edit, then its revert


async def test_edit_not_touching_the_trigger_keeps_the_job(live_scheduler, sets) -> None:
    """Re-arming would restart the interval from now and shift the next fire."""
    schedule = build_schedule()
    _arm(live_scheduler, schedule)
    next_fire = live_scheduler.get_job(str(schedule.id)).next_run_time

    await lifecycle.apply(schedule, {"description": "renamed"})

    job = live_scheduler.get_job(str(schedule.id))
    assert job.next_run_time == next_fire
    assert job.trigger.interval == timedelta(seconds=60)  # the job armed above, untouched
    assert sets[0]["description"] == "renamed"


def _past_one_shot(**overrides) -> Schedule:
    return build_schedule(
        trigger_type=TriggerType.DATE,
        trigger_args={"run_date": datetime.now(UTC) - timedelta(days=1)},
        **overrides,
    )


async def test_resume_of_expired_one_shot_is_rejected(live_scheduler, sets) -> None:
    schedule = _past_one_shot(status=ScheduleStatus.PAUSED)

    with pytest.raises(ValidationError, match="no future fire"):
        await lifecycle.apply(schedule, {"status": ScheduleStatus.ACTIVE})

    assert sets == []
    assert schedule.status == ScheduleStatus.PAUSED
    assert live_scheduler.get_jobs() == []


async def test_create_of_expired_one_shot_is_rejected(live_scheduler, monkeypatch) -> None:
    inserted: list[Schedule] = []

    async def _insert(self):
        inserted.append(self)

    monkeypatch.setattr(Schedule, "insert", _insert)

    with pytest.raises(ValidationError, match="no future fire"):
        await lifecycle.create(_past_one_shot())

    assert inserted == []


async def test_create_arms_active_schedule(live_scheduler, monkeypatch) -> None:
    async def _insert(self):
        return self

    monkeypatch.setattr(Schedule, "insert", _insert)
    schedule = build_schedule()

    await lifecycle.create(schedule)

    assert live_scheduler.get_job(str(schedule.id)) is not None


async def test_delete_disarms(live_scheduler, monkeypatch) -> None:
    async def _delete(self):
        return None

    monkeypatch.setattr(Schedule, "delete", _delete)
    schedule = build_schedule()
    _arm(live_scheduler, schedule)

    await lifecycle.delete(schedule)
    await lifecycle.delete(schedule)  # no job left: still fine

    assert live_scheduler.get_jobs() == []


# --- pause_if_failing: auto-pause ---------------------------------------------


async def test_auto_pause_disarms_when_the_threshold_matches(live_scheduler, updates) -> None:
    schedule = build_schedule()
    _arm(live_scheduler, schedule)

    await lifecycle.pause_if_failing(schedule.id)

    assert updates.updates[0]["$set"]["status"] == ScheduleStatus.PAUSED
    assert live_scheduler.get_job(str(schedule.id)) is None


async def test_auto_pause_below_threshold_keeps_job(live_scheduler, updates) -> None:
    """No match on the conditional pause (below threshold, or already paused)."""
    updates.modified = 0
    schedule = build_schedule()
    _arm(live_scheduler, schedule)

    await lifecycle.pause_if_failing(schedule.id)

    assert live_scheduler.get_job(str(schedule.id)) is not None


# --- resync_jobs --------------------------------------------------------------


def _patch_find(monkeypatch: pytest.MonkeyPatch, *schedules: Schedule) -> None:
    """Make ``Schedule.find(...).to_list()`` return the given documents."""

    class _FakeFind:
        async def to_list(self) -> list[Schedule]:
            return list(schedules)

    monkeypatch.setattr(Schedule, "find", classmethod(lambda cls, *a, **k: _FakeFind()))


def _job_ids(scheduler) -> list[str]:
    return [job.id for job in scheduler.get_jobs()]


async def test_resync_arms_active_schedule_without_a_job(monkeypatch, live_scheduler) -> None:
    schedule = build_schedule()
    _patch_find(monkeypatch, schedule)

    counts = await resync_jobs()

    assert _job_ids(live_scheduler) == [str(schedule.id)]
    assert counts == {"restored": 1, "skipped": 0, "failed": 0}


async def test_resync_leaves_already_armed_schedule_alone(monkeypatch, live_scheduler) -> None:
    schedule = build_schedule()
    _arm(live_scheduler, schedule)
    _patch_find(monkeypatch, schedule)

    counts = await resync_jobs()

    assert counts == {"restored": 0, "skipped": 1, "failed": 0}


async def test_resync_skips_one_shot_whose_time_has_passed(monkeypatch, live_scheduler) -> None:
    """Re-arming a past date trigger would fire the webhook again as a misfire."""
    schedule = build_schedule(
        trigger_type=TriggerType.DATE,
        trigger_args={"run_date": datetime.now(UTC) - timedelta(days=1)},
    )
    _patch_find(monkeypatch, schedule)

    counts = await resync_jobs()

    assert _job_ids(live_scheduler) == []
    assert counts["skipped"] == 1


async def test_resync_continues_past_a_broken_schedule(monkeypatch, live_scheduler) -> None:
    broken = build_schedule(name="broken", timezone="Mars/Phobos")
    healthy = build_schedule(name="healthy")
    _patch_find(monkeypatch, broken, healthy)

    counts = await resync_jobs()

    assert _job_ids(live_scheduler) == [str(healthy.id)]
    assert counts == {"restored": 1, "skipped": 0, "failed": 1}
