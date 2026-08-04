# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the job executor: the seam between the scheduler and the action."""

import pytest
from beanie import PydanticObjectId

from src.core.db.db_schema import RunStatus, Schedule, ScheduleRun
from src.scheduling import jobs
from src.scheduling.actions import WebhookError, WebhookResult
from tests.factories import build_schedule


def _stub_schedule_get(monkeypatch: pytest.MonkeyPatch, schedule):
    async def _get(_id) -> Schedule | None:
        return schedule

    monkeypatch.setattr(Schedule, "get", _get)


def _capture_insert(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    async def _insert(self) -> None:
        captured["run"] = self

    monkeypatch.setattr(ScheduleRun, "insert", _insert)


def _stub_save(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    async def _save(self) -> None:
        captured["saved"] = self

    monkeypatch.setattr(Schedule, "save", _save)


async def test_malformed_id_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _capture_insert(monkeypatch, captured)
    _stub_save(monkeypatch, captured)

    await jobs.execute_schedule("not-an-objectid")

    assert captured == {}


async def test_missing_schedule_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _stub_schedule_get(monkeypatch, None)
    _capture_insert(monkeypatch, captured)
    _stub_save(monkeypatch, captured)

    await jobs.execute_schedule(str(PydanticObjectId()))

    assert captured == {}


async def test_success_path_records_run_and_updates_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule = build_schedule()
    captured: dict = {}
    _stub_schedule_get(monkeypatch, schedule)
    monkeypatch.setattr(jobs, "run_action", lambda s: _result(200, "ok"))
    monkeypatch.setattr(jobs, "notify", _notify_true)
    _capture_insert(monkeypatch, captured)
    _stub_save(monkeypatch, captured)

    await jobs.execute_schedule(str(schedule.id))

    run = captured["run"]
    assert run.status == RunStatus.SUCCESS
    assert run.http_status == 200
    assert run.response_body == "ok"
    assert run.notified is True
    assert schedule.last_status == RunStatus.SUCCESS
    assert schedule.last_http_status == 200


async def test_webhook_error_records_error_run(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule = build_schedule()
    captured: dict = {}
    _stub_schedule_get(monkeypatch, schedule)

    def _raise(_s):
        raise WebhookError("boom", http_status=500, body="oops")

    monkeypatch.setattr(jobs, "run_action", _raise)
    monkeypatch.setattr(jobs, "notify", _notify_true)
    _capture_insert(monkeypatch, captured)
    _stub_save(monkeypatch, captured)

    await jobs.execute_schedule(str(schedule.id))

    run = captured["run"]
    assert run.status == RunStatus.ERROR
    assert run.error == "boom"
    assert run.http_status == 500
    assert run.response_body == "oops"
    assert schedule.last_status == RunStatus.ERROR
    assert schedule.last_error == "boom"


async def test_unexpected_exception_never_crashes_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule = build_schedule()
    captured: dict = {}
    _stub_schedule_get(monkeypatch, schedule)

    def _raise(_s):
        raise ValueError("kaboom")

    monkeypatch.setattr(jobs, "run_action", _raise)
    monkeypatch.setattr(jobs, "notify", _notify_true)
    _capture_insert(monkeypatch, captured)
    _stub_save(monkeypatch, captured)

    await jobs.execute_schedule(str(schedule.id))

    run = captured["run"]
    assert run.status == RunStatus.ERROR
    assert run.error == "kaboom"


async def _notify_true(_s, _r) -> bool:
    return True


async def _result(http_status: int, body: str) -> WebhookResult:
    return WebhookResult(http_status=http_status, body=body)
