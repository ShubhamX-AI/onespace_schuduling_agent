# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Schedule endpoints: hardening (never a 500) and response contracts."""

import pytest
from httpx import AsyncClient

from src.core.db.db_schema import Schedule
from tests.factories import build_schedule


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


@pytest.mark.parametrize("field", ["timezone", "trigger_type", "trigger_args", "name", "action"])
async def test_patch_null_on_required_field_returns_422(client: AsyncClient, field: str) -> None:
    """Explicit null on a field a schedule cannot lack is a client error, not a 500."""
    response = await client.patch(f"/api/v1/schedules/{'0' * 24}", json={field: None})

    assert response.status_code == 422
    assert response.json()["success"] is False


async def test_validate_mixed_aware_and_naive_window_is_not_a_500(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/schedules/validate",
        json={
            "trigger_type": "interval",
            "trigger_args": {"seconds": 30},
            "start_date": "2099-09-01T00:00:00Z",
            "end_date": "2099-09-02T00:00:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


async def test_validate_rejects_a_trigger_that_never_fires_again(client: AsyncClient) -> None:
    """Same rule as create: a past one-shot is not reported valid."""
    response = await client.post(
        "/api/v1/schedules/validate",
        json={"trigger_type": "date", "trigger_args": {"run_date": "2020-01-01T00:00:00Z"}},
    )

    assert response.status_code == 200  # documented: read `success`
    assert response.json()["success"] is False
    assert "no future fire" in response.json()["message"]


async def test_validate_checks_the_active_window(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/schedules/validate",
        json={
            "trigger_type": "interval",
            "trigger_args": {"seconds": 30},
            "start_date": "2026-09-01T00:00:00Z",
            "end_date": "2026-07-01T00:00:00Z",
        },
    )

    assert response.status_code == 200  # documented: read `success`
    assert response.json() == {
        "success": False,
        "message": "start_date must be before end_date",
        "data": None,
    }


async def test_run_now_returns_202_without_waiting_for_the_run(
    client: AsyncClient, live_scheduler, monkeypatch: pytest.MonkeyPatch
) -> None:
    schedule = build_schedule()

    async def _get(_id):
        return schedule

    monkeypatch.setattr(Schedule, "get", _get)

    response = await client.post(f"/api/v1/schedules/{schedule.id}/run")

    assert response.status_code == 202
    assert response.json()["message"] == "Schedule run queued"
    assert live_scheduler.get_job(f"run-now:{schedule.id}") is not None
