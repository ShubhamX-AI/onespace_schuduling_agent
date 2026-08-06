# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""GET /health — one deep probe of every dependency a request needs.

Always answers HTTP 200: a degraded dependency shows up in the body, never as a
5xx, so one blip cannot pull every instance of this service out of load-balancer
rotation at once. Monitor ``data.status``, not the status code.

No auth and no ``X-Owner-Id``: this is a probe, not an API, so it is mounted
outside the versioned prefix the schedule endpoints live under.
"""

import asyncio
import time
from collections.abc import Coroutine

from fastapi import APIRouter, Request

from src.api.models.response_schemas import ApiResponse
from src.core.db.db_connect import ping_db
from src.core.logging.logger import get_logger
from src.scheduling.scheduler import ping_scheduler

logger = get_logger(__name__)
router = APIRouter()

_STARTED = time.monotonic()


async def _timed(coro: Coroutine, timeout_s: float) -> dict:
    """Run one probe under the health timeout, reporting ok/latency.

    The broad ``except`` is deliberate: one broken probe must never 500 the
    endpoint whose whole job is to report breakage.
    """
    started = time.perf_counter()
    error = None
    try:
        async with asyncio.timeout(timeout_s):
            await coro
    except TimeoutError:
        error = f"TimeoutError: no answer within {timeout_s}s"
    except Exception as exc:
        # Error type + message only — never a URI, credential, or token.
        error = f"{type(exc).__name__}: {exc}"
    result = {"ok": error is None, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    if error:
        result["error"] = error
    return result


@router.get("/health", tags=["health"], response_model=ApiResponse[dict])
async def health(request: Request) -> ApiResponse[dict]:
    timeout_s = request.app.state.settings.health_probe_timeout_s
    probes = {"mongodb": ping_db(), "scheduler": ping_scheduler()}
    results = await asyncio.gather(*(_timed(c, timeout_s) for c in probes.values()))
    checks = dict(zip(probes, results, strict=True))

    healthy = all(check["ok"] for check in checks.values())
    if not healthy:
        logger.warning("health degraded: %s", [name for name, c in checks.items() if not c["ok"]])
    status = "ok" if healthy else "degraded"
    return ApiResponse(
        success=healthy,
        message=status,
        data={
            "status": status,
            "version": request.app.state.settings.app_version,
            "uptime_s": round(time.monotonic() - _STARTED, 1),
            "checks": checks,
        },
    )
