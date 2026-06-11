"""Schedule document — persisted definition of a scheduled job."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, HttpUrl
from pymongo import IndexModel

from app.core.config import get_settings


class TriggerType(StrEnum):
    DATE = "date"
    INTERVAL = "interval"
    CRON = "cron"


class ActionType(StrEnum):
    WEBHOOK = "webhook"


class WebhookAction(BaseModel):
    """What the scheduler does when a schedule fires: call an external HTTP API.

    The request body sent is the schedule's ``payload``. ``url`` is checked for
    SSRF (private/loopback hosts) at call time, not here.
    """

    type: ActionType = ActionType.WEBHOOK
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    # Extra attempts after the first on failure (non-2xx / timeout), with backoff.
    max_retries: int = Field(default=3, ge=0, le=10)


class ScheduleStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class RunStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Schedule(Document):
    name: str
    description: str | None = None
    trigger_type: TriggerType
    # Trigger args passed straight to APScheduler, e.g.
    # {"seconds": 30} for interval, {"hour": 9, "minute": 0} for cron.
    trigger_args: dict[str, Any] = Field(default_factory=dict)
    # IANA timezone the trigger is evaluated in (e.g. "America/New_York").
    # Makes firing independent of the server's local timezone.
    timezone: str = "UTC"
    # Optional active window — the schedule only fires between these instants.
    start_date: datetime | None = None
    end_date: datetime | None = None
    # Arbitrary payload handed to the job executor when the schedule fires.
    # For a webhook action this is sent as the request body.
    payload: dict[str, Any] = Field(default_factory=dict)
    # What to do on fire. Optional so legacy/log-only docs still load; new
    # schedules require it via ScheduleCreate.
    action: WebhookAction | None = None
    # Optional callback: after each run the service POSTs the result here.
    notify_url: HttpUrl | None = None
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    # Summary of the most recent run (full history lives in ScheduleRun).
    last_run_at: datetime | None = None
    last_status: RunStatus | None = None
    last_error: str | None = None
    last_http_status: int | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "schedules"
        indexes = [
            IndexModel([("name", pymongo.ASCENDING)], unique=True),
            IndexModel([("status", pymongo.ASCENDING)]),
        ]

    def touch(self) -> None:
        self.updated_at = _utcnow()


def _run_indexes() -> list[IndexModel]:
    """Indexes for ScheduleRun: per-schedule newest-first, plus an optional TTL."""
    indexes = [
        IndexModel([("schedule_id", pymongo.ASCENDING), ("finished_at", pymongo.DESCENDING)])
    ]
    ttl_days = get_settings().run_history_ttl_days
    if ttl_days > 0:
        indexes.append(
            IndexModel([("finished_at", pymongo.ASCENDING)], expireAfterSeconds=ttl_days * 86400)
        )
    return indexes


class ScheduleRun(Document):
    """One record per fire — the outcome of a single run (never overwritten)."""

    schedule_id: PydanticObjectId
    status: RunStatus
    # HTTP status the webhook returned (None if the call never completed).
    http_status: int | None = None
    # Truncated response body, for debugging (capped by webhook_response_max_chars).
    response_body: str | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime
    # Whether the notify callback was delivered (only meaningful if notify_url set).
    notified: bool = False

    class Settings:
        name = "schedule_runs"
        indexes = _run_indexes()


# Beanie document models registered on startup (see app/db/mongodb.py).
DOCUMENT_MODELS = [Schedule, ScheduleRun]
