# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Unit tests for trigger construction and startup job resync.

Both fake their seams (scheduler + ``Schedule.find``) — no DB, no live scheduler.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.core.db.db_schema import Schedule, TriggerType
from src.core.exceptions import ValidationError
from src.scheduling import schedule_service
from src.scheduling.schedule_service import build_trigger, resync_jobs
from tests.factories import build_schedule


def test_cron_trigger_uses_given_timezone() -> None:
    trigger = build_trigger(TriggerType.CRON, {"hour": 9, "minute": 0}, timezone="America/New_York")
    assert str(trigger.timezone) == "America/New_York"


def test_interval_trigger_builds() -> None:
    trigger = build_trigger(TriggerType.INTERVAL, {"seconds": 30})
    assert str(trigger.timezone) == "UTC"


def test_unknown_timezone_rejected() -> None:
    with pytest.raises(ValidationError):
        build_trigger(TriggerType.CRON, {"hour": 9}, timezone="Mars/Phobos")


def test_bad_trigger_args_rejected() -> None:
    with pytest.raises(ValidationError):
        build_trigger(TriggerType.CRON, {"hour": 99})


def test_start_after_end_rejected() -> None:
    start = datetime(2026, 9, 1)
    end = datetime(2026, 7, 1)
    with pytest.raises(ValidationError):
        build_trigger(TriggerType.INTERVAL, {"seconds": 30}, start_date=start, end_date=end)


class _FakeScheduler:
    """Records what resync arms; ``existing`` are the jobs already in the store."""

    def __init__(self, existing: tuple[str, ...] = ()) -> None:
        self.existing = set(existing)
        self.added: list[str] = []

    def get_job(self, job_id: str):
        return object() if job_id in self.existing else None

    def add_job(self, func, trigger=None, id=None, kwargs=None, replace_existing=False) -> None:
        self.added.append(id)


@pytest.fixture
def fake_scheduler(monkeypatch: pytest.MonkeyPatch) -> _FakeScheduler:
    scheduler = _FakeScheduler()
    monkeypatch.setattr(schedule_service, "get_scheduler", lambda: scheduler)
    return scheduler


def _patch_find(monkeypatch: pytest.MonkeyPatch, *schedules: Schedule) -> None:
    """Make ``Schedule.find(...).to_list()`` return the given documents."""

    class _FakeFind:
        async def to_list(self) -> list[Schedule]:
            return list(schedules)

    monkeypatch.setattr(Schedule, "find", classmethod(lambda cls, *a, **k: _FakeFind()))


async def test_resync_arms_active_schedule_without_a_job(
    monkeypatch: pytest.MonkeyPatch, fake_scheduler: _FakeScheduler
) -> None:
    schedule = build_schedule()
    _patch_find(monkeypatch, schedule)

    counts = await resync_jobs()

    assert fake_scheduler.added == [str(schedule.id)]
    assert counts == {"restored": 1, "skipped": 0, "failed": 0}


async def test_resync_leaves_already_armed_schedule_alone(
    monkeypatch: pytest.MonkeyPatch, fake_scheduler: _FakeScheduler
) -> None:
    schedule = build_schedule()
    fake_scheduler.existing.add(str(schedule.id))
    _patch_find(monkeypatch, schedule)

    counts = await resync_jobs()

    assert fake_scheduler.added == []
    assert counts["skipped"] == 1


async def test_resync_skips_one_shot_whose_time_has_passed(
    monkeypatch: pytest.MonkeyPatch, fake_scheduler: _FakeScheduler
) -> None:
    """Re-arming a past date trigger would fire the webhook again as a misfire."""
    schedule = build_schedule(
        trigger_type=TriggerType.DATE,
        trigger_args={"run_date": datetime.now(UTC) - timedelta(days=1)},
    )
    _patch_find(monkeypatch, schedule)

    counts = await resync_jobs()

    assert fake_scheduler.added == []
    assert counts["skipped"] == 1


async def test_resync_continues_past_a_broken_schedule(
    monkeypatch: pytest.MonkeyPatch, fake_scheduler: _FakeScheduler
) -> None:
    broken = build_schedule(name="broken", timezone="Mars/Phobos")
    healthy = build_schedule(name="healthy")
    _patch_find(monkeypatch, broken, healthy)

    counts = await resync_jobs()

    assert fake_scheduler.added == [str(healthy.id)]
    assert counts == {"restored": 1, "skipped": 0, "failed": 1}
