# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Input-validation rules on the request DTOs (pure Pydantic, no DB needed)."""

import pytest
from pydantic import ValidationError

from src.api.models.schedule import ScheduleCreate, ScheduleRead, ScheduleRunRead, ScheduleUpdate
from src.core.db.db_schema import WebhookAction
from tests.factories import build_schedule, build_schedule_run

_ACTION = {"type": "webhook", "url": "https://example.com/hook"}


def _create(**overrides):
    base = {"name": "job", "trigger_type": "interval", "action": _ACTION}
    return ScheduleCreate(**{**base, **overrides})


def test_valid_create_with_only_required_fields() -> None:
    schedule = _create()
    assert schedule.name == "job"
    assert schedule.timezone == "UTC"
    assert schedule.description is None


def test_blank_name_rejected() -> None:
    with pytest.raises(ValidationError):
        _create(name="   ")


def test_name_is_stripped() -> None:
    assert _create(name="  job  ").name == "job"


def test_blank_description_becomes_none() -> None:
    assert _create(description="   ").description is None


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        _create(timezzone="UTC")  # typo


def test_unknown_timezone_rejected() -> None:
    with pytest.raises(ValidationError):
        _create(timezone="Mars/Phobos")


def test_reserved_trigger_key_rejected() -> None:
    with pytest.raises(ValidationError):
        _create(trigger_args={"seconds": 5, "timezone": "UTC"})


def test_header_with_crlf_rejected() -> None:
    with pytest.raises(ValidationError):
        WebhookAction(url="https://example.com", headers={"X-Test": "a\r\nInjected: 1"})


def test_too_many_headers_rejected() -> None:
    headers = {f"H{i}": "v" for i in range(51)}
    with pytest.raises(ValidationError):
        WebhookAction(url="https://example.com", headers=headers)


def test_update_rename_is_cleaned() -> None:
    assert ScheduleUpdate(name="  renamed  ").name == "renamed"


def test_update_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        ScheduleUpdate(statuss="paused")  # typo


def test_update_absent_fields_stay_none() -> None:
    assert ScheduleUpdate().timezone is None
    assert ScheduleUpdate().trigger_args is None


def test_name_too_long_rejected() -> None:
    with pytest.raises(ValidationError):
        _create(name="x" * 129)


def test_description_too_long_rejected() -> None:
    with pytest.raises(ValidationError):
        _create(description="x" * 513)


def test_schedule_read_from_document() -> None:
    schedule = build_schedule()
    read = ScheduleRead.from_document(schedule, next_run_at=None)
    assert read.id == str(schedule.id)
    assert read.owner_id == "test-owner"
    assert read.name == "test-schedule"
    assert read.next_run_at is None
    assert read.action is not None


def test_schedule_run_read_from_document() -> None:
    run = build_schedule_run()
    read = ScheduleRunRead.from_document(run)
    assert read.id == str(run.id)
    assert read.schedule_id == str(run.schedule_id)
    assert read.status == run.status
    assert read.notified is False
