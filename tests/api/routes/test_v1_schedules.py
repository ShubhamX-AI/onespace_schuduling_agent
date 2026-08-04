# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Endpoint hardening: a malformed schedule id must not 500."""

import pytest
from httpx import AsyncClient


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/schedules/dwd"),
        ("delete", "/api/v1/schedules/dwd"),
        ("get", "/api/v1/schedules/dwd/runs"),
    ],
)
async def test_malformed_id_returns_404_envelope(
    client: AsyncClient, method: str, path: str
) -> None:
    response = await getattr(client, method)(path)

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert "not found" in body["message"].lower()
