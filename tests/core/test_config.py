# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for the Settings singleton: defaults, env overrides, and caching."""

import pytest

from src.core.config import Settings, configure, get_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "APP_NAME",
        "APP_ENV",
        "DEBUG",
        "API_V1_PREFIX",
        "LOG_LEVEL",
        "HOST",
        "PORT",
        "WORKERS",
        "MONGODB_URI",
        "MONGODB_DB",
        "SCHEDULER_JOBS_COLLECTION",
        "SCHEDULER_TIMEZONE",
        "WEBHOOK_ALLOW_PRIVATE_HOSTS",
        "WEBHOOK_RESPONSE_MAX_CHARS",
        "NOTIFY_TIMEOUT_SECONDS",
        "RUN_HISTORY_TTL_DAYS",
        "DOCS_SITE_DIR",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)  # defaults, not the developer's local .env
    assert settings.app_name == "OneSpace Scheduling Service"
    assert settings.app_env == "development"
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.port == 3011
    assert settings.mongodb_uri == "mongodb://localhost:27017"
    assert settings.mongodb_db == "onespace_scheduler_scheduling"
    assert settings.webhook_allow_private_hosts is False
    assert settings.run_history_ttl_days == 0
    assert settings.docs_site_dir == "site"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGODB_URI", "mongodb://override:27018")
    monkeypatch.setenv("MONGODB_DB", "onespace_override")
    monkeypatch.setenv("WEBHOOK_ALLOW_PRIVATE_HOSTS", "true")
    settings = Settings()
    assert settings.mongodb_uri == "mongodb://override:27018"
    assert settings.mongodb_db == "onespace_override"
    assert settings.webhook_allow_private_hosts is True


@pytest.mark.parametrize(
    ("app_env", "expected"),
    [("production", True), ("development", False), ("staging", False)],
)
def test_is_production(app_env: str, expected: bool) -> None:
    assert Settings(app_env=app_env).is_production is expected


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_configure_installs_settings_for_every_caller() -> None:
    settings = Settings(app_name="Configured")
    configure(settings)
    assert get_settings() is settings


def test_configure_none_rereads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(Settings())
    monkeypatch.setenv("APP_NAME", "Override")
    configure(None)
    assert get_settings().app_name == "Override"
