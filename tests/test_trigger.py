"""Unit tests for timezone-aware trigger construction (no DB/scheduler needed)."""

import pytest

from app.core.exceptions import ValidationError
from app.models.schedule import TriggerType
from app.services.schedule_service import build_trigger


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
    from datetime import datetime

    start = datetime(2026, 9, 1)
    end = datetime(2026, 7, 1)
    with pytest.raises(ValidationError):
        build_trigger(TriggerType.INTERVAL, {"seconds": 30}, start_date=start, end_date=end)
