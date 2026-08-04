# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the Mongo connection lifecycle: connect, close, and ping."""

import pytest

from src.core.config import Settings
from src.core.db import db_connect
from src.core.db.db_connect import db


class _FakeAdmin:
    async def command(self, command: str) -> dict:
        assert command == "ping"
        return {"ok": 1}


class _FakeDatabase:
    def __init__(self, name: str) -> None:
        self.name = name
        self.admin = _FakeAdmin()


class _FakeClient:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.closed = False

    def __getitem__(self, name: str) -> _FakeDatabase:
        return _FakeDatabase(name)

    @property
    def admin(self) -> _FakeAdmin:
        return _FakeAdmin()

    async def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_db():
    db.client = None
    db.database = None
    yield
    db.client = None
    db.database = None


async def test_ping_false_when_not_connected() -> None:
    assert await db_connect.ping() is False


async def test_ping_true_when_connected() -> None:
    db.client = _FakeClient("mongodb://localhost:27017")
    assert await db_connect.ping() is True


async def test_connect_to_mongo_sets_db(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient("mongodb://x:27017")
    init_calls = []

    async def _fake_init(**kwargs) -> None:
        init_calls.append(kwargs)

    monkeypatch.setattr(db_connect, "AsyncMongoClient", lambda uri: fake)
    monkeypatch.setattr("beanie.init_beanie", _fake_init)

    await db_connect.connect_to_mongo(Settings(mongodb_uri="mongodb://x:27017", mongodb_db="db_x"))

    assert db.client is fake
    assert db.database.name == "db_x"
    assert init_calls[0]["document_models"] is not None


async def test_close_mongo_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient("mongodb://x:27017")
    monkeypatch.setattr(db_connect, "AsyncMongoClient", lambda uri: fake)
    init_calls = []

    async def _fake_init(**kwargs) -> None:
        init_calls.append(kwargs)

    monkeypatch.setattr("beanie.init_beanie", _fake_init)

    await db_connect.connect_to_mongo(Settings())
    assert db.client is fake

    await db_connect.close_mongo_connection()
    assert fake.closed is True
    assert db.client is None
    assert db.database is None
