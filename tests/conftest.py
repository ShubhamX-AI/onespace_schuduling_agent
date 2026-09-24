# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Shared test fixtures.

Patches the MongoDB and scheduler lifecycle so the app can be exercised without
a live MongoDB. Seams are faked at the boundary (see the python-testing skill) —
no test ever dials out, and the ``no_network`` autouse fixture makes an unmocked
outbound call fail loudly.
"""

import socket
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from httpx import ASGITransport, AsyncClient

from server import create_app
from src.core.config import Settings


class _FakeMongoDatabase:
    """AsyncDatabase stand-in for ``init_beanie``: lets tests build real Beanie
    documents offline (via ``tests.factories``). Never touches the network.
    """

    def __init__(self) -> None:
        self.client = MagicMock()
        self.client.append_metadata = MagicMock()

    def __getitem__(self, name: str) -> MagicMock:
        return MagicMock()

    def get_collection(self, name: str) -> MagicMock:
        return MagicMock()

    async def command(self, command: str) -> dict:
        return {"version": "8.0", "ok": 1}

    async def list_collection_names(self, **kwargs) -> list[str]:
        return ["onespace_scheduler_schedules", "onespace_scheduler_schedule_runs"]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _beanie_init() -> None:
    from beanie import init_beanie

    from src.core.db.db_schema import DOCUMENT_MODELS

    await init_beanie(
        database=_FakeMongoDatabase(), document_models=DOCUMENT_MODELS, skip_indexes=True
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn any unmocked outbound connection into an AssertionError.

    Tests that need a client use ``httpx.MockTransport`` (or patch the seam
    entirely); a test that reaches the real network is missing a mock.

    Loopback is allowed — it is how the event loop creates its internal
    self-pipe on Windows, not an outbound call.
    """

    _LOOPBACK = ("127.0.0.1", "::1")

    def _host(address) -> str | None:
        return address[0] if isinstance(address, tuple) else None

    def _block_connect(self, address, *args, **kwargs):
        if _host(address) in _LOOPBACK:
            return _real_connect(self, address, *args, **kwargs)
        raise AssertionError("Unmocked outbound HTTP call attempted (network disabled)")

    def _block_connect_ex(self, address, *args, **kwargs):
        if _host(address) in _LOOPBACK:
            return _real_connect_ex(self, address, *args, **kwargs)
        raise AssertionError("Unmocked outbound HTTP call attempted (network disabled)")

    def _block_create_connection(address, *args, **kwargs):
        if _host(address) in _LOOPBACK:
            return _real_create_connection(address, *args, **kwargs)
        raise AssertionError("Unmocked outbound HTTP call attempted (network disabled)")

    _real_connect = socket.socket.connect
    _real_connect_ex = socket.socket.connect_ex
    _real_create_connection = socket.create_connection
    monkeypatch.setattr(socket.socket, "connect", _block_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _block_connect_ex)
    monkeypatch.setattr(socket, "create_connection", _block_create_connection)


@pytest.fixture(autouse=True)
def _reset_settings() -> None:
    """``create_app`` and tests install Settings globally; drop them after each test."""
    from src.core import config

    yield
    config.configure(None)


@pytest.fixture
async def live_scheduler(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncIOScheduler]:
    """A real AsyncIOScheduler on the default in-memory jobstore, installed as the
    shared scheduler. Started paused, so jobs are stored but never fire."""
    from src.scheduling import scheduler as scheduler_module

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.start(paused=True)
    monkeypatch.setattr(scheduler_module, "_scheduler", scheduler)
    yield scheduler
    scheduler.shutdown(wait=False)


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test", mongodb_db="onespace_scheduler_scheduling_test")


@pytest.fixture
async def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    async def _noop_mongo(_: Settings) -> None:
        return None

    async def _noop_close() -> None:
        return None

    def _noop_scheduler(_: Settings):
        return None

    async def _noop_resync() -> dict[str, int]:
        return {"restored": 0, "skipped": 0, "failed": 0}

    monkeypatch.setattr("server.connect_to_mongo", _noop_mongo)
    monkeypatch.setattr("server.close_mongo_connection", _noop_close)
    monkeypatch.setattr("server.start_scheduler", _noop_scheduler)
    monkeypatch.setattr("server.resync_jobs", _noop_resync)
    monkeypatch.setattr("server.shutdown_scheduler", lambda: None)

    app = create_app(settings)
    transport = ASGITransport(app=app)
    # Every schedule endpoint requires an owner; send one by default.
    headers = {"X-Owner-Id": "test-owner"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        async with app.router.lifespan_context(app):
            yield ac
