# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Smoke + envelope-shape tests for the API."""

from httpx import AsyncClient


async def test_validation_error_uses_envelope(client: AsyncClient) -> None:
    # Empty body -> FastAPI validation error, served in the standard envelope.
    resp = await client.post("/api/v1/schedules", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "Validation failed"
    assert isinstance(body["data"], list)
    assert "field" in body["data"][0]


async def test_unknown_route_uses_envelope(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
