"""Request/response DTOs for schedules — the API contract."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.schedule import (
    RunStatus,
    Schedule,
    ScheduleRun,
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
    # Optional callback: the run result is POSTed here after each fire.
    notify_url: HttpUrl | None = None


class ScheduleUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=512)
    trigger_type: TriggerType | None = None
    trigger_args: dict[str, Any] | None = None
    timezone: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    payload: dict[str, Any] | None = None
    action: WebhookAction | None = None
    notify_url: HttpUrl | None = None
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
    trigger_type: TriggerType
    trigger_args: dict[str, Any] = Field(default_factory=dict)
    timezone: str = "UTC"
