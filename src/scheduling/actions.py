# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""What a schedule *does* when it fires.

One action type today: ``webhook`` — an outbound HTTP call to another service.
The call is hardened against SSRF (private/loopback targets are blocked unless
``settings.webhook_allow_private_hosts`` is set) and retried with exponential
backoff on failure. The HTTP status and a truncated response body are captured
so the run can be recorded and the creator notified.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Any

import httpx

from src.core.config import get_settings
from src.core.db.db_schema import Schedule, ScheduleRun, WebhookAction
from src.core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ActionResult:
    """Outcome of a fired action: HTTP status, truncated response body, and the
    error message when it failed (``None`` on success)."""

    http_status: int | None = None
    body: str | None = None
    error: str | None = None


class WebhookError(Exception):
    """A webhook could not be delivered. Carries the response when one arrived."""

    def __init__(self, message: str, http_status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.http_status = http_status
        self.body = body


async def run_action(schedule: Schedule) -> ActionResult:
    """Perform the schedule's action. Never raises: a failure is ``result.error``.

    No action set => log only (legacy).
    """
    action = schedule.action
    if action is None:
        # Never log the payload: it is tenant data.
        logger.info("Schedule %s fired with no action", schedule.id)
        return ActionResult()
    try:
        return await _call_webhook(action, schedule.payload)
    except WebhookError as exc:
        # An expected delivery failure: the message is already secret-free.
        logger.warning("Schedule %s failed: %s", schedule.id, exc)
        return ActionResult(exc.http_status, exc.body, str(exc))
    except Exception as exc:  # never crash the scheduler
        logger.exception("Schedule %s failed", schedule.id)
        # The recorded error reaches run history and the notify callback, so it
        # carries only the type: an arbitrary message may hold secrets.
        return ActionResult(error=f"Unexpected error: {type(exc).__name__}")


async def _call_webhook(action: WebhookAction, body: dict[str, Any]) -> ActionResult:
    """Send the HTTP request, retrying with backoff. Raises on final failure."""
    url = str(action.url)
    await _assert_safe_url(url)

    attempts = action.max_retries + 1
    async with httpx.AsyncClient(timeout=action.timeout_seconds) as client:
        for attempt in range(attempts):
            try:
                response = await client.request(
                    action.method, url, headers=action.headers, json=body
                )
                response.raise_for_status()
                return ActionResult(response.status_code, _truncate(response.text))
            except httpx.HTTPError as exc:
                if attempt + 1 == attempts:
                    http_status, resp_body = _response_of(exc)
                    raise WebhookError(
                        _failure_message(action.method, url, exc, http_status),
                        http_status,
                        resp_body,
                    ) from exc
                await asyncio.sleep(2**attempt)  # 1s, 2s, 4s, ...


async def notify(schedule: Schedule, run: ScheduleRun) -> bool:
    """Best-effort callback: POST the run result to notify_url. Never raises."""
    if schedule.notify_url is None:
        return False
    url = str(schedule.notify_url)
    result = {
        "schedule_id": str(schedule.id),
        "name": schedule.name,
        "status": run.status,
        "http_status": run.http_status,
        "error": run.error,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat(),
    }
    try:
        await _assert_safe_url(url)
        async with httpx.AsyncClient(timeout=get_settings().notify_timeout_seconds) as client:
            response = await client.post(url, json=result)
            response.raise_for_status()
        return True
    except Exception as exc:  # a broken callback must never fail the run
        # Type only: the exception text and traceback repeat the notify URL.
        logger.warning("Notify failed for schedule %s: %s", schedule.id, type(exc).__name__)
        return False


def _failure_message(method: str, url: str, exc: Exception, http_status: int | None) -> str:
    """Describe a failed call without secrets.

    Built from scheme, host and path only: the query string and userinfo can
    hold tokens, and httpx's own message repeats the full URL. The text is
    stored in ``last_error`` and run history and sent to the notify callback.
    """
    target = httpx.URL(url).copy_with(query=None, fragment=None, username=None, password=None)
    message = f"{method} {target} failed: {type(exc).__name__}"
    if http_status is not None:
        message += f" (HTTP {http_status})"
    return message


def _truncate(text: str) -> str:
    return text[: get_settings().webhook_response_max_chars]


def _response_of(exc: httpx.HTTPError) -> tuple[int | None, str | None]:
    """Pull the status + truncated body off an error, when the call got a response."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code, _truncate(exc.response.text)
    return None, None


async def _assert_safe_url(url: str) -> None:
    """Reject targets that resolve to loopback/private/reserved IPs (SSRF guard)."""
    if get_settings().webhook_allow_private_hosts:
        return

    request = httpx.URL(url)
    if request.scheme not in ("http", "https"):
        raise WebhookError(f"Unsupported URL scheme: {request.scheme}")

    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(request.host, request.port, proto=socket.IPPROTO_TCP)
    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
            raise WebhookError(f"Blocked webhook target {request.host} -> {ip} (private host)")
