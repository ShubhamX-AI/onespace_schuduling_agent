"""What a schedule *does* when it fires.

One action type today: ``webhook`` — an outbound HTTP call to another service.
The call is hardened against SSRF (private/loopback targets are blocked unless
``settings.webhook_allow_private_hosts`` is set) and retried with exponential
backoff on failure.
"""

import asyncio
import ipaddress
import socket
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schedule import Schedule, WebhookAction

logger = get_logger(__name__)


class WebhookError(Exception):
    """A webhook action could not be delivered (blocked, timed out, or non-2xx)."""


async def run_action(schedule: Schedule) -> None:
    """Perform the schedule's action. No action set => log only (legacy)."""
    action = schedule.action
    if action is None:
        logger.info("Schedule %s fired with no action; payload=%s", schedule.id, schedule.payload)
        return
    await _call_webhook(action, schedule.payload)


async def _call_webhook(action: WebhookAction, body: dict[str, Any]) -> None:
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
                return
            except httpx.HTTPError as exc:
                if attempt + 1 == attempts:
                    raise WebhookError(f"{action.method} {url} failed: {exc}") from exc
                await asyncio.sleep(2**attempt)  # 1s, 2s, 4s, ...


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
