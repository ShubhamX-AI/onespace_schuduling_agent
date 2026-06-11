"""Smoke + envelope-shape tests for the API."""

from httpx import AsyncClient


async def test_health_uses_envelope(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["success"], bool)
    assert "message" in body
    assert "database" in body["data"]


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
