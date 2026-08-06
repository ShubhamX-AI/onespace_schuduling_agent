# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for GET /health.

The probe helpers are patched as the health module resolves them, so these run
offline and stay independent of the MongoDB driver and the scheduler.
"""

import asyncio

import pytest
from httpx import AsyncClient

from src.api.routes import health
from src.core.config import Settings


@pytest.fixture(autouse=True)
def probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """All dependencies healthy by default; individual tests override one."""

    async def _ok() -> None:
        return None

    monkeypatch.setattr(health, "ping_db", _ok)
    monkeypatch.setattr(health, "ping_scheduler", _ok)


def _fail(error: Exception):
    async def _probe() -> None:
        raise error

    return _probe


async def test_all_dependencies_up(client: AsyncClient) -> None:
    resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["status"] == "ok"
    assert data["version"] == Settings().app_version
    assert data["uptime_s"] >= 0
    assert set(data["checks"]) == {"mongodb", "scheduler"}
    assert all(check["ok"] for check in data["checks"].values())
    assert all("latency_ms" in check for check in data["checks"].values())


async def test_needs_no_owner_header(settings: Settings) -> None:
    """The probe is mounted outside the tenant-scoped API prefix."""
    from httpx import ASGITransport

    from server import create_app

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


async def test_database_down_degrades_but_returns_200(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "ping_db", _fail(RuntimeError("no reply")))

    resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    data = body["data"]
    assert data["status"] == "degraded"
    assert data["checks"]["mongodb"]["error"] == "RuntimeError: no reply"
    assert data["checks"]["scheduler"]["ok"] is True  # peers unaffected


async def test_scheduler_stopped_degrades(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "ping_scheduler", _fail(RuntimeError("scheduler not running")))

    data = (await client.get("/health")).json()["data"]

    assert data["status"] == "degraded"
    assert "RuntimeError" in data["checks"]["scheduler"]["error"]


async def test_a_hanging_probe_times_out_instead_of_hanging_the_endpoint() -> None:
    result = await health._timed(asyncio.sleep(5), timeout_s=0.01)

    assert result["ok"] is False
    assert result["error"].startswith("TimeoutError")


def test_probe_timeout_default_is_short() -> None:
    """Far below the timeouts sized for real calls (e.g. notify at 10s)."""
    assert Settings().health_probe_timeout_s == 3.0
