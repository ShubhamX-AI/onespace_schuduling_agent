# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the aggregate v1 router: every endpoint group is mounted."""

from src.api.routes.v1.router import api_router


def _route_paths() -> list[str]:
    return [route.path for route in api_router.routes]


def test_schedule_endpoints_mounted() -> None:
    paths = _route_paths()
    assert "/schedules" in paths
    assert "/schedules/{schedule_id}" in paths
    assert "/schedules/{schedule_id}/runs" in paths


def test_schedules_prefix_is_applied() -> None:
    assert any(path.startswith("/schedules") for path in _route_paths())
