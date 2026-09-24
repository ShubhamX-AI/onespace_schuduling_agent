# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the error hierarchy and the central exception handlers."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pymongo.errors import DuplicateKeyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.testclient import TestClient

from src.core.exceptions import (
    AppError,
    AuthError,
    ConflictError,
    NotFoundError,
    ValidationError,
    register_exception_handlers,
)


@pytest.mark.parametrize(
    ("exc_cls", "status"),
    [
        (AppError, 500),
        (AuthError, 401),
        (NotFoundError, 404),
        (ConflictError, 409),
        (ValidationError, 422),
    ],
)
def test_status_code_mapping(exc_cls, status: int) -> None:
    assert exc_cls().status_code == status


def test_message_default_and_override() -> None:
    assert AppError().message == "Internal server error"
    assert NotFoundError("gone").message == "gone"
    assert str(AppError("boom")) == "boom"


async def test_handlers_emit_envelope() -> None:
    app = FastAPI()

    @app.get("/app-error")
    async def _app_error():
        raise NotFoundError("nope")

    @app.get("/http-error")
    async def _http_error():
        raise StarletteHTTPException(status_code=418, detail="teapot")

    @app.get("/duplicate")
    async def _duplicate():
        raise DuplicateKeyError("E11000 duplicate key error")

    register_exception_handlers(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/app-error")
        assert response.status_code == 404
        assert response.json() == {"success": False, "message": "nope", "data": None}

        response = await ac.get("/http-error")
        assert response.status_code == 418
        body = response.json()
        assert body["success"] is False
        assert body["data"] is None
        assert "teapot" in body["message"]

        response = await ac.get("/duplicate")  # name race past the service check
        assert response.status_code == 409
        assert response.json() == {
            "success": False,
            "message": "Schedule name already exists",
            "data": None,
        }


def test_unhandled_error_returns_500_envelope() -> None:
    app = FastAPI()

    @app.get("/boom")
    def _boom():
        raise ValueError("unexpected")

    register_exception_handlers(app)
    # raise_server_exceptions=False: Starlette's server middleware always
    # re-raises after the handler runs, so the client must be allowed to
    # receive the response.
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"success": False, "message": "Internal server error", "data": None}


async def test_validation_error_lists_fields() -> None:
    app = FastAPI()

    @app.get("/validate")
    async def _validate(required: str):
        return {"ok": required}

    register_exception_handlers(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/validate")
        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["data"][0]["field"] == "query.required"
