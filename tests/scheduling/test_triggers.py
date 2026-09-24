# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Unit tests for trigger construction."""

from datetime import UTC, datetime, timedelta

import pytest

from src.api.models.schedule import ScheduleUpdate
from src.core.db.db_schema import Schedule, TriggerType
from src.core.exceptions import ValidationError
from src.scheduling.triggers import (
    TRIGGER_FIELDS,
    TriggerSpec,
    armable_trigger,
    build_trigger,
    has_future_fire,
)


def _spec(trigger_type, trigger_args, timezone="UTC", start_date=None, end_date=None):
    """Unvalidated, like a document loaded from the DB: build_trigger's own checks run."""
    return TriggerSpec.model_construct(
        trigger_type=trigger_type,
        trigger_args=trigger_args,
        timezone=timezone,
        start_date=start_date,
        end_date=end_date,
    )


def test_cron_trigger_uses_given_timezone() -> None:
    trigger = build_trigger(_spec(TriggerType.CRON, {"hour": 9, "minute": 0}, "America/New_York"))
    assert str(trigger.timezone) == "America/New_York"


def test_interval_trigger_builds() -> None:
    trigger = build_trigger(_spec(TriggerType.INTERVAL, {"seconds": 30}))
    assert str(trigger.timezone) == "UTC"


def test_unknown_timezone_rejected() -> None:
    with pytest.raises(ValidationError):
        build_trigger(_spec(TriggerType.CRON, {"hour": 9}, "Mars/Phobos"))


def test_bad_trigger_args_rejected() -> None:
    with pytest.raises(ValidationError):
        build_trigger(_spec(TriggerType.CRON, {"hour": 99}))


def test_start_after_end_rejected() -> None:
    start = datetime(2026, 9, 1)
    end = datetime(2026, 7, 1)
    with pytest.raises(ValidationError):
        build_trigger(_spec(TriggerType.INTERVAL, {"seconds": 30}, start_date=start, end_date=end))


def test_mixed_aware_and_naive_window_is_compared_in_schedule_timezone() -> None:
    """A naive bound is wall time in the schedule's timezone, not a TypeError."""
    start = datetime(2026, 9, 1, 12, tzinfo=UTC)
    naive_end = datetime(2026, 9, 1, 13)  # 13:00 Kolkata = 07:30 UTC, before start

    with pytest.raises(ValidationError):
        build_trigger(
            _spec(TriggerType.INTERVAL, {"seconds": 30}, "Asia/Kolkata", start, naive_end)
        )
    trigger = build_trigger(_spec(TriggerType.INTERVAL, {"seconds": 30}, "UTC", start, naive_end))
    assert trigger.end_date.hour == 13


def test_reserved_trigger_key_rejected() -> None:
    """Applies to stored documents too, not only API requests (resync path)."""
    with pytest.raises(ValidationError):
        build_trigger(_spec(TriggerType.INTERVAL, {"seconds": 30, "timezone": "UTC"}))


def test_armable_trigger_rejects_a_past_one_shot() -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    spec = _spec(TriggerType.DATE, {"run_date": past})

    assert not has_future_fire(build_trigger(spec), datetime.now(UTC))
    with pytest.raises(ValidationError, match="no future fire"):
        armable_trigger(spec)


def test_armable_trigger_accepts_a_future_fire() -> None:
    assert armable_trigger(_spec(TriggerType.INTERVAL, {"seconds": 30})) is not None


def test_trigger_fields_exist_on_every_model_that_carries_them() -> None:
    """lifecycle.apply re-arms on TRIGGER_FIELDS; a field missing here would skip re-arm."""
    assert TRIGGER_FIELDS <= Schedule.model_fields.keys()
    assert TRIGGER_FIELDS <= ScheduleUpdate.model_fields.keys()
