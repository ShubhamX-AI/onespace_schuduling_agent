# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the Run module: one fire, driven through ``execute_schedule``.

The webhook goes through ``httpx.MockTransport``; Beanie reads and writes are
faked and recorded (no live MongoDB), so tests assert what each fire writes.
"""

from types import SimpleNamespace

import httpx
import pytest
from beanie import PydanticObjectId

from src.core.db.db_schema import RunStatus, Schedule, ScheduleRun, ScheduleStatus
from src.scheduling import jobs
from tests.factories import build_schedule
from tests.scheduling.test_actions import _allow_private, _mock_client


class _FakeDb:
    """Records every write one fire makes. ``modified`` is what the conditional
    auto-pause update reports as matched."""

    def __init__(self, schedule: Schedule | None) -> None:
        self.schedule = schedule
        self.updates: list[dict] = []
        self.runs: list[ScheduleRun] = []
        self.modified = 0

    def find_one(self, *_filters):
        return self

    async def update(self, update: dict):
        self.updates.append(update)
        return SimpleNamespace(modified_count=self.modified)


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> _FakeDb:
    fake = _FakeDb(build_schedule())

    async def _get(_id) -> Schedule | None:
        return fake.schedule

    async def _insert(self) -> None:
        fake.runs.append(self)

    monkeypatch.setattr(Schedule, "get", _get)
    monkeypatch.setattr(Schedule, "find_one", classmethod(lambda cls, *f: fake.find_one(*f)))
    monkeypatch.setattr(ScheduleRun, "insert", _insert)
    return fake


@pytest.fixture
def webhook(monkeypatch: pytest.MonkeyPatch):
    """Answer webhook (and notify) calls with ``webhook.response``."""
    _allow_private(monkeypatch, True)
    state = SimpleNamespace(response=httpx.Response(200, text="ok"))
    _mock_client(monkeypatch, lambda request: state.response)
    return state


async def test_malformed_id_is_skipped(db: _FakeDb) -> None:
    await jobs.execute_schedule("not-an-objectid")

    assert db.updates == [] and db.runs == []


async def test_missing_schedule_is_skipped(db: _FakeDb) -> None:
    db.schedule = None

    await jobs.execute_schedule(str(PydanticObjectId()))

    assert db.updates == [] and db.runs == []


async def test_success_records_run_and_resets_errors(db: _FakeDb, webhook) -> None:
    await jobs.execute_schedule(str(db.schedule.id))

    (run,) = db.runs
    assert (run.status, run.http_status, run.response_body) == (RunStatus.SUCCESS, 200, "ok")
    assert run.started_at <= run.finished_at
    assert db.updates == [
        {
            "$set": {
                "last_run_at": run.finished_at,
                "last_status": RunStatus.SUCCESS,
                "last_error": None,
                "last_http_status": 200,
                "consecutive_errors": 0,
            }
        }
    ]


async def test_failed_webhook_counts_an_error_and_checks_auto_pause(db: _FakeDb, webhook) -> None:
    db.schedule.action.max_retries = 0
    webhook.response = httpx.Response(500, text="oops")

    await jobs.execute_schedule(str(db.schedule.id))

    (run,) = db.runs
    assert (run.status, run.http_status, run.response_body) == (RunStatus.ERROR, 500, "oops")
    summary, pause = db.updates
    assert summary["$inc"] == {"consecutive_errors": 1}
    assert pause["$set"]["status"] == ScheduleStatus.PAUSED  # conditional; matched nothing here


async def test_notify_result_is_stored_on_the_run(db: _FakeDb, webhook) -> None:
    db.schedule.notify_url = "http://127.0.0.1/cb"

    await jobs.execute_schedule(str(db.schedule.id))

    assert db.runs[0].notified is True


async def test_failed_history_insert_still_counts_the_error(
    db: _FakeDb, webhook, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The summary (and so auto-pause) must not depend on the best-effort insert."""
    db.schedule.action.max_retries = 0
    webhook.response = httpx.Response(500)

    async def _failing_insert(self) -> None:
        raise RuntimeError("mongo down")

    monkeypatch.setattr(ScheduleRun, "insert", _failing_insert)

    await jobs.execute_schedule(str(db.schedule.id))  # does not raise

    assert db.updates[0]["$inc"] == {"consecutive_errors": 1}
