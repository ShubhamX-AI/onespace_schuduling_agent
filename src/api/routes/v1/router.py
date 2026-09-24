# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Aggregate v1 routers."""

from fastapi import APIRouter

from src.api.routes.v1 import schedules

api_router = APIRouter()
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
