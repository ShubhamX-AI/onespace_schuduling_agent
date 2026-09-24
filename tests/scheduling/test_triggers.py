# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Unit tests for trigger construction."""

from datetime import UTC, datetime

import pytest

from src.core.db.db_schema import TriggerType
from src.core.exceptions import ValidationError
from src.scheduling.triggers import build_trigger


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


def test_mixed_aware_and_naive_window_is_compared_in_schedule_timezone() -> None:
    """A naive bound is wall time in the schedule's timezone, not a TypeError."""
    start = datetime(2026, 9, 1, 12, tzinfo=UTC)
    naive_end = datetime(2026, 9, 1, 13)  # 13:00 Kolkata = 07:30 UTC, before start

    with pytest.raises(ValidationError):
        build_trigger(
            TriggerType.INTERVAL,
            {"seconds": 30},
            "Asia/Kolkata",
            start_date=start,
            end_date=naive_end,
        )
    trigger = build_trigger(TriggerType.INTERVAL, {"seconds": 30}, "UTC", start, naive_end)
    assert trigger.end_date.hour == 13


def test_reserved_trigger_key_rejected() -> None:
    """Applies to stored documents too, not only API requests (resync path)."""
    with pytest.raises(ValidationError):
        build_trigger(TriggerType.INTERVAL, {"seconds": 30, "timezone": "UTC"})
