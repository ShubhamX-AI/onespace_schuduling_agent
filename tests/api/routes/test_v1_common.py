# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Owner scoping: endpoints require an X-Owner-Id header."""

import pytest
from httpx import AsyncClient


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/schedules"),
        ("get", "/api/v1/schedules/dwd"),
        ("delete", "/api/v1/schedules/dwd"),
    ],
)
async def test_missing_owner_header_returns_401_envelope(
    client: AsyncClient, method: str, path: str
) -> None:
    # Blank out the default header to simulate a caller that sent none.
    response = await getattr(client, method)(path, headers={"X-Owner-Id": ""})

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert "x-owner-id" in body["message"].lower()


async def test_validate_endpoint_needs_no_owner(client: AsyncClient) -> None:
    # /validate is stateless (nothing persisted), so it stays open.
    response = await client.post(
        "/api/v1/schedules/validate",
        headers={"X-Owner-Id": ""},
        json={"trigger_type": "interval", "trigger_args": {"seconds": 30}},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
