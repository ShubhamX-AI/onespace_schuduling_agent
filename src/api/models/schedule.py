# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Request/response DTOs for schedules — the API contract."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, field_validator

from src.core.db.db_schema import (
    MASKED_VALUE,
    RunStatus,
    Schedule,
    ScheduleRun,
    ScheduleStatus,
    TriggerType,
    WebhookAction,
)
from src.scheduling.triggers import TriggerSpec, timezone_field, trigger_args_field

_MAX_NAME_LEN = 128
_MAX_DESCRIPTION_LEN = 512


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


def _to_str(value: Any) -> str:
    return str(value)


class ScheduleCreate(TriggerSpec):
    # Trigger fields, their rules and extra="forbid" come from TriggerSpec.
    name: str
    description: str | None = None
    # The action's request body, kept top-level (not inside `action`) so it is
    # shared by every action type. For a webhook it is sent as the JSON body.
    # See docs/concepts/actions.md.
    payload: dict[str, Any] = Field(default_factory=dict)
    # What to fire when the trigger hits.
    action: WebhookAction
    # Optional callback: the run result is POSTed here after each fire.
    notify_url: HttpUrl | None = None

    _clean_name = field_validator("name")(_clean_name)
    _clean_description = field_validator("description")(_clean_optional_text)


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

    # A schedule cannot exist without these: omit one to leave it unchanged,
    # an explicit null is a 422. Nullable fields (description, window,
    # notify_url) accept null to clear them.
    @field_validator(
        "name",
        "trigger_type",
        "trigger_args",
        "timezone",
        "payload",
        "action",
        "status",
        mode="before",
    )
    @classmethod
    def _not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("must not be null; omit the field to leave it unchanged")
        return value

    # Same rules as create; only run when the field is provided.
    _clean_name = field_validator("name")(_clean_name)
    _clean_description = field_validator("description")(_clean_optional_text)
    _timezone_field = field_validator("timezone")(timezone_field)
    _trigger_args_field = field_validator("trigger_args")(trigger_args_field)


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
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
    next_run_at: datetime | None = None
    last_run_at: datetime | None
    last_status: RunStatus | None
    last_error: str | None
    last_http_status: int | None
    consecutive_errors: int
    created_at: datetime
    updated_at: datetime

    # Document ids are ObjectIds; the API exposes them as strings.
    _id_to_str = field_validator("id", mode="before")(_to_str)

    @field_serializer("action")
    def _mask_header_values(self, action: WebhookAction | None) -> WebhookAction | None:
        """Keep header names, hide values: they usually hold the target's credentials."""
        if action is None:
            return None
        return action.model_copy(update={"headers": dict.fromkeys(action.headers, MASKED_VALUE)})

    @classmethod
    def from_document(cls, doc: Schedule, next_run_at: datetime | None = None) -> "ScheduleRead":
        return cls.model_validate(doc).model_copy(update={"next_run_at": next_run_at})


class ScheduleRunRead(BaseModel):
    """A single run's outcome, returned by GET /schedules/{id}/runs."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    schedule_id: str
    status: RunStatus
    http_status: int | None
    response_body: str | None
    error: str | None
    started_at: datetime
    finished_at: datetime
    notified: bool

    _ids_to_str = field_validator("id", "schedule_id", mode="before")(_to_str)

    @classmethod
    def from_document(cls, doc: ScheduleRun) -> "ScheduleRunRead":
        return cls.model_validate(doc)
