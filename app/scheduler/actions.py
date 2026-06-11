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

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schedule import Schedule, ScheduleRun, WebhookAction

logger = get_logger(__name__)


@dataclass
class WebhookResult:
    """Outcome of a webhook call: the HTTP status and a truncated response body."""

    http_status: int | None = None
    body: str | None = None


class WebhookError(Exception):
    """A webhook could not be delivered. Carries the response when one arrived."""

    def __init__(self, message: str, http_status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.http_status = http_status
        self.body = body


async def run_action(schedule: Schedule) -> WebhookResult:
    """Perform the schedule's action. No action set => log only (legacy)."""
    action = schedule.action
    if action is None:
        logger.info("Schedule %s fired with no action; payload=%s", schedule.id, schedule.payload)
        return WebhookResult()
    return await _call_webhook(action, schedule.payload)


async def _call_webhook(action: WebhookAction, body: dict[str, Any]) -> WebhookResult:
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
                return WebhookResult(response.status_code, _truncate(response.text))
            except httpx.HTTPError as exc:
                if attempt + 1 == attempts:
                    http_status, resp_body = _response_of(exc)
                    raise WebhookError(
                        f"{action.method} {url} failed: {exc}", http_status, resp_body
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
    except Exception:  # a broken callback must never fail the run
        logger.exception("Notify failed for schedule %s", schedule.id)
        return False


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
