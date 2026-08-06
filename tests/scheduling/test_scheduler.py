# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the shared APScheduler lifecycle: start, get, shutdown."""

import pytest

from src.core.config import Settings
from src.scheduling import scheduler
from src.scheduling.scheduler import (
    get_scheduler,
    ping_scheduler,
    shutdown_scheduler,
    start_scheduler,
)


class _FakeJobStore:
    def __init__(self, *args, **kwargs) -> None:
        pass


class _FakeScheduler:
    def __init__(self, timezone=None) -> None:
        self.timezone = timezone
        self.jobstores: dict[str, object] = {}
        self.started = False
        self.running = False
        self.stopped = False
        self.shutdown_wait = True

    def add_jobstore(self, jobstore, alias="default") -> None:
        self.jobstores[alias] = jobstore

    def start(self) -> None:
        self.started = True
        self.running = True

    def shutdown(self, wait=True) -> None:
        self.running = False
        self.stopped = True
        self.shutdown_wait = wait


@pytest.fixture(autouse=True)
def _reset_scheduler(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(scheduler, "_scheduler", None)
    yield
    monkeypatch.setattr(scheduler, "_scheduler", None)


def test_start_scheduler_creates_and_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "MongoDBJobStore", _FakeJobStore)
    monkeypatch.setattr(scheduler, "AsyncIOScheduler", _FakeScheduler)

    started = start_scheduler(Settings(scheduler_timezone="Asia/Kolkata"))

    assert isinstance(started, _FakeScheduler)
    assert started.started is True
    assert str(started.timezone) == "Asia/Kolkata"
    assert isinstance(started.jobstores["default"], _FakeJobStore)


def test_start_scheduler_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "MongoDBJobStore", _FakeJobStore)
    monkeypatch.setattr(scheduler, "AsyncIOScheduler", _FakeScheduler)

    first = start_scheduler(Settings())
    second = start_scheduler(Settings())

    assert first is second


def test_get_scheduler_raises_when_not_started() -> None:
    with pytest.raises(RuntimeError, match="Scheduler not started"):
        get_scheduler()


def test_shutdown_stops_and_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "MongoDBJobStore", _FakeJobStore)
    monkeypatch.setattr(scheduler, "AsyncIOScheduler", _FakeScheduler)

    started = start_scheduler(Settings())
    shutdown_scheduler(wait=False)

    assert started.stopped is True
    assert started.shutdown_wait is False
    with pytest.raises(RuntimeError):
        get_scheduler()


async def test_ping_scheduler_raises_when_not_started() -> None:
    with pytest.raises(RuntimeError, match="scheduler not running"):
        await ping_scheduler()


async def test_ping_scheduler_passes_when_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "MongoDBJobStore", _FakeJobStore)
    monkeypatch.setattr(scheduler, "AsyncIOScheduler", _FakeScheduler)
    start_scheduler(Settings())

    assert await ping_scheduler() is None
