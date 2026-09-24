# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the Beanie document models and their indexes."""

import pytest
from pydantic import ValidationError

from src.core.db import db_schema
from src.core.db.db_schema import (
    DOCUMENT_MODELS,
    Schedule,
    ScheduleRun,
    ScheduleStatus,
    TriggerType,
    WebhookAction,
)


def test_webhook_action_defaults() -> None:
    action = WebhookAction(url="https://example.com/hook")
    assert action.method == "POST"
    assert action.timeout_seconds == 30.0
    assert action.max_retries == 3
    assert action.headers == {}


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Test": "a\r\nInjected: 1"},
        {"X-Test\nB": "v"},
        {"\x00": "v"},
    ],
)
def test_webhook_header_control_characters_rejected(headers) -> None:
    with pytest.raises(ValidationError):
        WebhookAction(url="https://example.com", headers=headers)


def test_webhook_empty_header_name_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        WebhookAction(url="https://example.com", headers={"": "v"})


def test_webhook_header_length_caps() -> None:
    with pytest.raises(ValidationError):
        WebhookAction(url="https://example.com", headers={"X-Test": "x" * 1025})
    with pytest.raises(ValidationError):
        WebhookAction(url="https://example.com", headers={"X" * 1025: "v"})


def test_webhook_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        WebhookAction(url="https://example.com", timeout_seconds=0)
    with pytest.raises(ValidationError):
        WebhookAction(url="https://example.com", timeout_seconds=301)
    with pytest.raises(ValidationError):
        WebhookAction(url="https://example.com", max_retries=11)


def test_schedule_defaults() -> None:
    schedule = Schedule(name="x", trigger_type=TriggerType.INTERVAL)
    assert schedule.owner_id == "public"
    assert schedule.timezone == "UTC"
    assert schedule.status == ScheduleStatus.ACTIVE


def test_schedule_collection_and_indexes() -> None:
    assert Schedule.Settings.name == "onespace_scheduler_schedules"
    assert ScheduleRun.Settings.name == "onespace_scheduler_schedule_runs"
    assert DOCUMENT_MODELS == [Schedule, ScheduleRun]

    indexes = Schedule.Settings.indexes
    assert len(indexes) == 2
    unique_owner_name = next(i for i in indexes if i.document["unique"])
    assert unique_owner_name.document["key"] == {"owner_id": 1, "name": 1}


def test_run_indexes_without_ttl() -> None:
    indexes = db_schema.run_indexes(0)
    assert len(indexes) == 1
    assert not any(i.document.get("expireAfterSeconds") for i in indexes)


def test_run_indexes_with_ttl() -> None:
    indexes = db_schema.run_indexes(7)
    ttl = next(i for i in indexes if i.document.get("expireAfterSeconds"))
    assert ttl.document["expireAfterSeconds"] == 7 * 86400
    assert ttl.document["key"] == {"finished_at": 1}
