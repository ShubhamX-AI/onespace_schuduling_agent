"""Shared API dependencies."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Header

from app.core.exceptions import AuthError
from app.scheduler.scheduler import get_scheduler


def scheduler_dep() -> AsyncIOScheduler:
    return get_scheduler()


def current_owner(x_owner_id: str | None = Header(default=None)) -> str:
    """Identify the caller from the X-Owner-Id header; schedules are scoped to it.

    Logical partitioning, not security: the header is trusted as-is (an upstream
    gateway is expected to set it). A missing or blank header is a 401.
    """
    owner = (x_owner_id or "").strip()
    if not owner:
        raise AuthError("Missing X-Owner-Id header")
    return owner
