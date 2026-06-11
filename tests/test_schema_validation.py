"""Input-validation rules on the request DTOs (pure Pydantic, no DB needed)."""

import pytest
from pydantic import ValidationError

from app.models.schedule import WebhookAction
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate

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
