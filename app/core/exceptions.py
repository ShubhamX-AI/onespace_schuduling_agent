"""Domain exceptions and FastAPI exception handlers.

All handlers emit the standard envelope (see ``app.schemas.response``):
``{"success": false, "message": ..., "data": ...}``.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base application error mapped to an HTTP response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    message = "Resource not found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    message = "Resource conflict"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = "Validation failed"


def _envelope(status_code: int, message: str, data: Any = None) -> JSONResponse:
    """Build an error response in the standard envelope shape."""
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "data": data},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register handlers so every error response uses the standard envelope."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.status_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in err["loc"]), "error": err["msg"]}
            for err in exc.errors()
        ]
        return _envelope(status.HTTP_422_UNPROCESSABLE_CONTENT, "Validation failed", errors)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(exc.status_code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return _envelope(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
