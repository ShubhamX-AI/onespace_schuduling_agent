"""Shared API dependencies.

Thin for now (no auth). Add reusable Depends() providers here as the API grows.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scheduler.scheduler import get_scheduler


def scheduler_dep() -> AsyncIOScheduler:
    return get_scheduler()
