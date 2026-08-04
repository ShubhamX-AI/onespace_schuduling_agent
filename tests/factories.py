# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Model builders for tests — one factory per request/definition model.

Reuse these instead of re-building a schedule by hand in each test. A factory
kwarg beats a new fixture.
"""

from datetime import UTC, datetime

from beanie import PydanticObjectId

from src.api.models.schedule import ScheduleCreate, ScheduleUpdate
from src.core.db.db_schema import (
    Schedule,
    ScheduleRun,
    ScheduleStatus,
    TriggerType,
    WebhookAction,
)


def build_webhook_action(**overrides) -> WebhookAction:
    data = {"url": "https://example.com/hook"}
    data.update(overrides)
    return WebhookAction(**data)


def build_schedule_create(**overrides) -> ScheduleCreate:
    data = {
        "name": "test-schedule",
        "trigger_type": TriggerType.INTERVAL,
        "trigger_args": {"seconds": 60},
        "timezone": "UTC",
        "payload": {"key": "value"},
        "action": build_webhook_action(),
    }
    data.update(overrides)
    return ScheduleCreate(**data)


def build_schedule_update(**overrides) -> ScheduleUpdate:
    data = {"name": "renamed"}
    data.update(overrides)
    return ScheduleUpdate(**data)


def build_schedule(**overrides) -> Schedule:
    """A Schedule document, defaulting to the fields a live one would carry."""
    data = {
        "id": PydanticObjectId(),
        "owner_id": "test-owner",
        "name": "test-schedule",
        "trigger_type": TriggerType.INTERVAL,
        "trigger_args": {"seconds": 60},
        "timezone": "UTC",
        "payload": {"key": "value"},
        "action": build_webhook_action(),
        "status": ScheduleStatus.ACTIVE,
    }
    data.update(overrides)
    return Schedule(**data)


def build_schedule_run(**overrides) -> ScheduleRun:
    now = datetime.now(UTC)
    data = {
        "schedule_id": PydanticObjectId(),
        "status": "success",
        "started_at": now,
        "finished_at": now,
    }
    data.update(overrides)
    return ScheduleRun(**data)
