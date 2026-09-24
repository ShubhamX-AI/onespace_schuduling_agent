# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Trigger rules and timezone-aware APScheduler trigger construction.

Every trigger rule lives here. ``TriggerSpec`` applies the per-field checks to
requests (for per-field 422s); ``build_trigger`` applies all of them again, so
documents loaded from the DB (e.g. by ``resync_jobs``) get the same rules as
requests. ``armable_trigger`` adds the one rule for arming: a future fire.
"""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.db.db_schema import TriggerType
from src.core.exceptions import ValidationError

_TRIGGER_BUILDERS = {
    TriggerType.DATE: DateTrigger,
    TriggerType.INTERVAL: IntervalTrigger,
    TriggerType.CRON: CronTrigger,
}
# DateTrigger fires once and has no active window.
_WINDOWED_TRIGGERS = {TriggerType.INTERVAL, TriggerType.CRON}

# Injected by build_trigger from the top-level fields; passing them inside
# trigger_args would be silently overridden, so they are rejected.
_RESERVED_TRIGGER_KEYS = {"timezone", "start_date", "end_date"}


def resolve_timezone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError(f"Unknown timezone '{timezone}'") from exc


def check_trigger_args(trigger_args: dict[str, Any]) -> dict[str, Any]:
    reserved = _RESERVED_TRIGGER_KEYS & trigger_args.keys()
    if reserved:
        raise ValidationError(f"trigger_args must not contain reserved keys: {sorted(reserved)}")
    return trigger_args


def _localize(value: datetime | None, tz: ZoneInfo) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value


# pydantic reports a ValueError against the offending field in the 422.
def timezone_field(value: str) -> str:
    value = value.strip()
    try:
        resolve_timezone(value)
    except ValidationError as exc:
        raise ValueError(exc.message) from None
    return value


def trigger_args_field(value: dict[str, Any]) -> dict[str, Any]:
    try:
        return check_trigger_args(value)
    except ValidationError as exc:
        raise ValueError(exc.message) from None


class TriggerSpec(BaseModel):
    """The WHEN of a schedule, as a request carries it. Shared by the API models."""

    # Reject unknown keys so client typos (e.g. "timezzone") error out loudly.
    model_config = ConfigDict(extra="forbid")

    trigger_type: TriggerType
    trigger_args: dict[str, Any] = Field(default_factory=dict)
    timezone: str = "UTC"
    start_date: datetime | None = None
    end_date: datetime | None = None

    _timezone_field = field_validator("timezone")(timezone_field)
    _trigger_args_field = field_validator("trigger_args")(trigger_args_field)


# Schedule fields that feed the trigger.
TRIGGER_FIELDS = frozenset(TriggerSpec.model_fields)


def build_trigger(spec):
    """Construct a timezone-aware APScheduler trigger from anything with the
    ``TriggerSpec`` fields (a ``TriggerSpec`` or a ``Schedule`` document).

    Raises ValidationError on a bad timezone, reserved or invalid trigger args,
    or a start_date not before end_date. The timezone makes
    firing independent of the host server's local clock.
    """
    tz = resolve_timezone(spec.timezone)
    # A naive date means wall time in the schedule's timezone (APScheduler's own
    # reading), so an aware and a naive bound can be compared.
    start_date, end_date = _localize(spec.start_date, tz), _localize(spec.end_date, tz)
    if start_date and end_date and start_date >= end_date:
        raise ValidationError("start_date must be before end_date")
    check_trigger_args(spec.trigger_args)
    args: dict[str, Any] = {**spec.trigger_args, "timezone": tz}
    if spec.trigger_type in _WINDOWED_TRIGGERS:
        args["start_date"] = start_date
        args["end_date"] = end_date
    try:
        return _TRIGGER_BUILDERS[spec.trigger_type](**args)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid trigger_args for {spec.trigger_type}: {exc}") from exc


def has_future_fire(trigger, now: datetime) -> bool:
    next_fire = trigger.get_next_fire_time(None, now)
    return next_fire is not None and next_fire >= now


def armable_trigger(spec):
    """``build_trigger``, plus ValidationError when the trigger would never fire
    again (e.g. a one-shot whose date has passed): arming it would only misfire."""
    trigger = build_trigger(spec)
    if not has_future_fire(trigger, datetime.now(UTC)):
        raise ValidationError("Trigger has no future fire")
    return trigger
