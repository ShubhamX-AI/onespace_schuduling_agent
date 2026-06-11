"""Request/response DTOs for schedules — the API contract."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.schedule import (
    RunStatus,
    Schedule,
    ScheduleRun,
    ScheduleStatus,
    TriggerType,
    WebhookAction,
)

_MAX_NAME_LEN = 128
_MAX_DESCRIPTION_LEN = 512
# Injected into the trigger separately by build_trigger; passing them inside
# trigger_args would be silently overridden, so reject them up front.
_RESERVED_TRIGGER_KEYS = {"timezone", "start_date", "end_date"}


def _clean_name(value: str) -> str:
    """Strip and require a non-empty name within the length cap."""
    value = value.strip()
    if not value:
        raise ValueError("name must not be blank")
    if len(value) > _MAX_NAME_LEN:
        raise ValueError(f"name exceeds {_MAX_NAME_LEN} characters")
    return value


def _clean_optional_text(value: str | None) -> str | None:
    """Strip free text; treat blank as absent (None)."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > _MAX_DESCRIPTION_LEN:
        raise ValueError(f"description exceeds {_MAX_DESCRIPTION_LEN} characters")
    return value


def _validate_timezone(value: str) -> str:
    """Accept only a resolvable IANA timezone (validated here, not deep in the service)."""
    value = value.strip()
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown timezone '{value}'") from exc
    return value


def _check_trigger_args(args: dict[str, Any]) -> dict[str, Any]:
    """Reject reserved keys that build_trigger injects itself."""
    reserved = _RESERVED_TRIGGER_KEYS & args.keys()
    if reserved:
        raise ValueError(f"trigger_args must not contain reserved keys: {sorted(reserved)}")
    return args


class ScheduleCreate(BaseModel):
    # Reject unknown keys so client typos (e.g. "timezzone") error out loudly.
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    trigger_type: TriggerType
    trigger_args: dict[str, Any] = Field(default_factory=dict)
    timezone: str = "UTC"
    start_date: datetime | None = None
    end_date: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    # What to fire when the trigger hits.
    action: WebhookAction
    # Optional callback: the run result is POSTed here after each fire.
    notify_url: HttpUrl | None = None

    _clean_name = field_validator("name")(_clean_name)
    _clean_description = field_validator("description")(_clean_optional_text)
    _validate_timezone = field_validator("timezone")(_validate_timezone)
    _check_trigger_args = field_validator("trigger_args")(_check_trigger_args)


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    trigger_type: TriggerType | None = None
    trigger_args: dict[str, Any] | None = None
    timezone: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    payload: dict[str, Any] | None = None
    action: WebhookAction | None = None
    notify_url: HttpUrl | None = None
    status: ScheduleStatus | None = None

    # Same rules as create, but only when the field is provided.
    _clean_description = field_validator("description")(_clean_optional_text)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        return _clean_name(value) if value is not None else None

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None) -> str | None:
        return _validate_timezone(value) if value is not None else None

    @field_validator("trigger_args")
    @classmethod
    def _check_trigger_args(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _check_trigger_args(value) if value is not None else None


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    trigger_type: TriggerType
    trigger_args: dict[str, Any]
    timezone: str
    start_date: datetime | None
    end_date: datetime | None
    payload: dict[str, Any]
    action: WebhookAction | None
    notify_url: HttpUrl | None
    status: ScheduleStatus
    # When the job fires next, read live from the scheduler (None if paused/expired).
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_status: RunStatus | None
    last_error: str | None
    last_http_status: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, doc: Schedule, next_run_at: datetime | None = None) -> "ScheduleRead":
        return cls(
            id=str(doc.id),
            name=doc.name,
            description=doc.description,
            trigger_type=doc.trigger_type,
            trigger_args=doc.trigger_args,
            timezone=doc.timezone,
            start_date=doc.start_date,
            end_date=doc.end_date,
            payload=doc.payload,
            action=doc.action,
            notify_url=doc.notify_url,
            status=doc.status,
            next_run_at=next_run_at,
            last_run_at=doc.last_run_at,
            last_status=doc.last_status,
            last_error=doc.last_error,
            last_http_status=doc.last_http_status,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class ScheduleRunRead(BaseModel):
    """A single run's outcome, returned by GET /schedules/{id}/runs."""

    id: str
    schedule_id: str
    status: RunStatus
    http_status: int | None
    response_body: str | None
    error: str | None
    started_at: datetime
    finished_at: datetime
    notified: bool

    @classmethod
    def from_document(cls, doc: ScheduleRun) -> "ScheduleRunRead":
        return cls(
            id=str(doc.id),
            schedule_id=str(doc.schedule_id),
            status=doc.status,
            http_status=doc.http_status,
            response_body=doc.response_body,
            error=doc.error,
            started_at=doc.started_at,
            finished_at=doc.finished_at,
            notified=doc.notified,
        )


class ValidateTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_type: TriggerType
    trigger_args: dict[str, Any] = Field(default_factory=dict)
    timezone: str = "UTC"

    _validate_timezone = field_validator("timezone")(_validate_timezone)
    _check_trigger_args = field_validator("trigger_args")(_check_trigger_args)
