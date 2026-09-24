# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Unit tests for the webhook action: validation, SSRF guard, retry, notify."""

from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError as PydanticValidationError

from src.api.models.schedule import ScheduleCreate, WebhookAction
from src.core.config import Settings, configure
from src.core.db.db_schema import RunStatus
from src.scheduling import actions
from src.scheduling.actions import WebhookError, _assert_safe_url, _call_webhook, notify, run_action
from tests.factories import build_schedule, build_webhook_action


def _allow_private(monkeypatch: pytest.MonkeyPatch, allow: bool, **overrides) -> None:
    """Install Settings for the SSRF guard (conftest resets them after the test)."""
    configure(Settings(webhook_allow_private_hosts=allow, **overrides))


# --- model / DTO validation ------------------------------------------------


def test_webhook_action_defaults() -> None:
    action = WebhookAction(url="https://example.com/hook")
    assert action.method == "POST"
    assert action.max_retries == 3
    assert action.timeout_seconds == 30.0


def test_schedule_create_requires_action() -> None:
    with pytest.raises(PydanticValidationError):
        ScheduleCreate(name="x", trigger_type="date")


# --- SSRF guard ------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/hook",  # loopback
        "http://10.0.0.5/hook",  # private
        "http://169.254.169.254/latest",  # link-local (cloud metadata)
    ],
)
async def test_ssrf_guard_blocks_private_hosts(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, False)
    with pytest.raises(WebhookError, match="private host"):
        await _assert_safe_url(url)


async def test_ssrf_guard_allows_public_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, False)
    await _assert_safe_url("http://8.8.8.8/hook")  # no raise


async def test_ssrf_guard_rejects_bad_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, False)
    with pytest.raises(WebhookError, match="scheme"):
        await _assert_safe_url("ftp://example.com")


async def test_ssrf_guard_skipped_when_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, True)
    await _assert_safe_url("http://127.0.0.1/hook")  # no raise


# --- retry / delivery ------------------------------------------------------


def _mock_client(monkeypatch: pytest.MonkeyPatch, handler) -> dict:
    """Route every webhook request through `handler`; return a call counter."""
    calls = {"n": 0}

    def counting(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return handler(request)

    transport = httpx.MockTransport(counting)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        actions.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=transport, timeout=kw.get("timeout")),
    )

    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(actions.asyncio, "sleep", _no_sleep)
    return calls


async def test_webhook_success_captures_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, True)
    calls = _mock_client(monkeypatch, lambda req: httpx.Response(200, text="pong"))
    action = WebhookAction(url="http://127.0.0.1/hook", max_retries=3)
    result = await _call_webhook(action, {"hello": "world"})
    assert calls["n"] == 1  # no retries needed
    assert result.http_status == 200
    assert result.body == "pong"


async def test_webhook_retries_then_fails_with_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, True)
    calls = _mock_client(monkeypatch, lambda req: httpx.Response(500, text="boom"))
    action = WebhookAction(url="http://127.0.0.1/hook", max_retries=2)
    with pytest.raises(WebhookError) as exc_info:
        await _call_webhook(action, {})
    assert calls["n"] == 3  # 1 initial + 2 retries
    assert exc_info.value.http_status == 500
    assert exc_info.value.body == "boom"


async def test_webhook_body_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, True, webhook_response_max_chars=5)
    _mock_client(monkeypatch, lambda req: httpx.Response(200, text="0123456789"))
    result = await _call_webhook(WebhookAction(url="http://127.0.0.1/hook"), {})
    assert result.body == "01234"


# --- notify (best-effort callback) -----------------------------------------


# notify() only reads a few attributes, so lightweight stand-ins avoid needing a
# live MongoDB to construct real Beanie documents.
def _run() -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        status=RunStatus.SUCCESS, http_status=None, error=None, started_at=now, finished_at=now
    )


def _schedule(notify_url: str | None) -> SimpleNamespace:
    return SimpleNamespace(id="abc", name="x", notify_url=notify_url)


async def test_notify_skipped_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, True)
    assert await notify(_schedule(None), _run()) is False


async def test_notify_posts_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, True)
    _mock_client(monkeypatch, lambda req: httpx.Response(200))
    assert await notify(_schedule("http://127.0.0.1/cb"), _run()) is True


async def test_notify_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, True)
    _mock_client(monkeypatch, lambda req: httpx.Response(500))
    assert await notify(_schedule("http://127.0.0.1/cb"), _run()) is False  # swallowed


# --- run_action (the seam jobs.py calls) ------------------------------------


async def test_run_action_without_action_returns_empty_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule = build_schedule(action=None)
    result = await run_action(schedule)
    assert result.http_status is None
    assert result.body is None


async def test_run_action_delegates_to_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, True)
    _mock_client(monkeypatch, lambda req: httpx.Response(200, text="pong"))
    schedule = build_schedule()
    result = await run_action(schedule)
    assert result.http_status == 200
    assert result.body == "pong"


async def test_run_action_failure_is_a_result_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_private(monkeypatch, True)
    _mock_client(monkeypatch, lambda req: httpx.Response(502, text="bad gateway"))
    schedule = build_schedule(action=build_webhook_action(max_retries=0))
    result = await run_action(schedule)
    assert (result.http_status, result.body) == (502, "bad gateway")
    assert "failed" in result.error


async def test_run_action_blocked_target_is_a_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_private(monkeypatch, False)
    schedule = build_schedule(action=build_webhook_action(url="http://127.0.0.1/hook"))
    result = await run_action(schedule)
    assert "private host" in result.error
    assert result.http_status is None


async def test_run_action_unexpected_error_is_a_result(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(*_args):
        raise ValueError("kaboom")

    monkeypatch.setattr(actions, "_call_webhook", _boom)
    result = await run_action(build_schedule())
    assert result.error == "kaboom"


def test_response_of_transport_error_has_no_response() -> None:
    exc = httpx.ConnectError("boom", request=httpx.Request("POST", "https://example.com"))
    assert actions._response_of(exc) == (None, None)
