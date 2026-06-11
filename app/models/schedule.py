"""Schedule document — persisted definition of a scheduled job."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import pymongo
from beanie import Document
from pydantic import Field
from pymongo import IndexModel


class TriggerType(StrEnum):
    DATE = "date"
    INTERVAL = "interval"
    CRON = "cron"


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
    payload: dict[str, Any] = Field(default_factory=dict)
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    # Outcome of the most recent run, recorded by the scheduler event listener.
    last_run_at: datetime | None = None
    last_status: RunStatus | None = None
    last_error: str | None = None
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
