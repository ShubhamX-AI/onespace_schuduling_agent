# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Liveness/readiness endpoint."""

from fastapi import APIRouter

from src.api.models.response_schemas import ApiResponse
from src.core.db.db_connect import ping

router = APIRouter()


@router.get("/health", response_model=ApiResponse[dict])
async def health() -> ApiResponse[dict]:
    db_ok = await ping()
    return ApiResponse(
        success=db_ok,
        message="ok" if db_ok else "degraded",
        data={"database": db_ok},
    )
