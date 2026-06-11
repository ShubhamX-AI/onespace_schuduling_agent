"""Shared test fixtures.

Patches the MongoDB and scheduler lifecycle so the app can be exercised
without a live MongoDB. Replace with a real test database (e.g. mongomock-motor
or a disposable Mongo container) when adding integration tests.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test", mongodb_db="onespace_scheduling_test")


@pytest.fixture
async def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    async def _noop_mongo(_: Settings) -> None:
        return None

    async def _noop_close() -> None:
        return None

    def _noop_scheduler(_: Settings):
        return None

    monkeypatch.setattr("app.main.connect_to_mongo", _noop_mongo)
    monkeypatch.setattr("app.main.close_mongo_connection", _noop_close)
    monkeypatch.setattr("app.main.start_scheduler", _noop_scheduler)
    monkeypatch.setattr("app.main.shutdown_scheduler", lambda: None)

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            yield ac
