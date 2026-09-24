# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Trigger rules and timezone-aware APScheduler trigger construction.

Every trigger rule lives here. The API models reuse these checks for per-field
422s; ``build_trigger`` applies all of them again, so documents loaded from the
DB (e.g. by ``resync_jobs``) get the same rules as requests.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.core.db.db_schema import Schedule, TriggerType
from src.core.exceptions import ValidationError

_TRIGGER_BUILDERS = {
    TriggerType.DATE: DateTrigger,
    TriggerType.INTERVAL: IntervalTrigger,
    TriggerType.CRON: CronTrigger,
}
# DateTrigger fires once and has no active window.
_WINDOWED_TRIGGERS = {TriggerType.INTERVAL, TriggerType.CRON}

# Schedule fields that feed the trigger.
TRIGGER_FIELDS = frozenset({"trigger_type", "trigger_args", "timezone", "start_date", "end_date"})
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


def build_trigger(
    trigger_type: TriggerType,
    trigger_args: dict[str, Any],
    timezone: str = "UTC",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Construct a timezone-aware APScheduler trigger.

    Raises ValidationError on a bad timezone, reserved or invalid trigger args,
    or a start_date not before end_date. The timezone makes
    firing independent of the host server's local clock.
    """
    tz = resolve_timezone(timezone)
    # A naive date means wall time in the schedule's timezone (APScheduler's own
    # reading), so an aware and a naive bound can be compared.
    start_date, end_date = _localize(start_date, tz), _localize(end_date, tz)
    if start_date and end_date and start_date >= end_date:
        raise ValidationError("start_date must be before end_date")
    check_trigger_args(trigger_args)
    args: dict[str, Any] = {**trigger_args, "timezone": tz}
    if trigger_type in _WINDOWED_TRIGGERS:
        args["start_date"] = start_date
        args["end_date"] = end_date
    try:
        return _TRIGGER_BUILDERS[trigger_type](**args)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid trigger_args for {trigger_type}: {exc}") from exc


def trigger_for(schedule: Schedule):
    return build_trigger(
        schedule.trigger_type,
        schedule.trigger_args,
        schedule.timezone,
        schedule.start_date,
        schedule.end_date,
    )
