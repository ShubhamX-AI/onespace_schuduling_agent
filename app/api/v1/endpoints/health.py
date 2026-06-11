"""Liveness/readiness endpoint."""

from fastapi import APIRouter

from app.db.mongodb import ping
from app.schemas.response import ApiResponse

router = APIRouter()


@router.get("/health", response_model=ApiResponse[dict])
async def health() -> ApiResponse[dict]:
    db_ok = await ping()
    return ApiResponse(
        success=db_ok,
        message="ok" if db_ok else "degraded",
        data={"database": db_ok},
    )
