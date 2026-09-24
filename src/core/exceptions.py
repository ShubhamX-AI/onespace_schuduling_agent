# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Domain exceptions and FastAPI exception handlers.

All handlers emit the standard envelope (see ``src.api.models.response_schemas``):
``{"success": false, "message": ..., "data": ...}``.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.logging.logger import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base application error mapped to an HTTP response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class AuthError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Not authenticated"


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

    # The service checks name uniqueness first; this catches the race where two
    # requests pass that check and the unique (owner_id, name) index rejects one.
    # ponytail: assumes that is the only unique index; name the index if more appear.
    @app.exception_handler(DuplicateKeyError)
    async def _handle_duplicate(_: Request, exc: DuplicateKeyError) -> JSONResponse:
        return _envelope(status.HTTP_409_CONFLICT, "Schedule name already exists")

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(exc.status_code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return _envelope(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
