"""Aggregate v1 routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, schedules

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
