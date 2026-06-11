"""Request/response DTOs for schedules — the API contract."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.schedule import (
    RunStatus,
    Schedule,
    ScheduleStatus,
    TriggerType,
    WebhookAction,
)


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    trigger_type: TriggerType
    trigger_args: dict[str, Any] = Field(default_factory=dict)
    timezone: str = "UTC"
    start_date: datetime | None = None
    end_date: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    # What to fire when the trigger hits.
    action: WebhookAction


class ScheduleUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=512)
    trigger_type: TriggerType | None = None
    trigger_args: dict[str, Any] | None = None
    timezone: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    payload: dict[str, Any] | None = None
    action: WebhookAction | None = None
    status: ScheduleStatus | None = None


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
    status: ScheduleStatus
    # When the job fires next, read live from the scheduler (None if paused/expired).
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_status: RunStatus | None
    last_error: str | None
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
            status=doc.status,
            next_run_at=next_run_at,
            last_run_at=doc.last_run_at,
            last_status=doc.last_status,
            last_error=doc.last_error,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class ValidateTriggerRequest(BaseModel):
    trigger_type: TriggerType
    trigger_args: dict[str, Any] = Field(default_factory=dict)
    timezone: str = "UTC"
