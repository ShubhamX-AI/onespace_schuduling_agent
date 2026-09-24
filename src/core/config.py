# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Application settings, loaded from environment / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "OneSpace Scheduling Service"
    # Single source of the service version: reported by /health and by the
    # OpenAPI metadata. Keep in step with the version in pyproject.toml.
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # Server (Granian in prod, uvicorn for dev)
    host: str = "0.0.0.0"
    port: int = 3011
    workers: int = 1

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "onespace_scheduler_scheduling"

    # Scheduler
    scheduler_jobs_collection: str = "onespace_scheduler_jobs"
    scheduler_timezone: str = "UTC"

    # Webhook actions
    # Allow webhook targets on loopback/private IPs. Off in prod (SSRF guard);
    # turn on in dev/test to hit a local listener.
    webhook_allow_private_hosts: bool = False
    # Max characters of a webhook's response body kept in the run record.
    webhook_response_max_chars: int = 2048
    # Timeout for the best-effort notify (callback) call.
    notify_timeout_seconds: float = 10.0
    # Days to keep run-history records (TTL index). 0 = keep forever.
    run_history_ttl_days: int = 0
    # Consecutive error threshold - pause schedules after this many consecutive errors
    consecutive_error_threshold: int = 50

    # Health
    # Per-probe timeout for GET /health. Deliberately far below the timeouts
    # sized for real calls — a probe that hangs is a probe nobody polls.
    health_probe_timeout_s: float = 3.0

    # Built MkDocs site, served at /documentation. Run `mkdocs build` to create
    # it; if the directory is absent the route is simply not mounted.
    docs_site_dir: str = "site"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


_settings: Settings | None = None


def configure(settings: Settings | None) -> None:
    """Install the Settings every ``get_settings()`` caller sees.

    ``create_app`` calls it, so settings passed to the app reach domain code too.
    ``None`` resets: the next ``get_settings()`` reads the environment again.
    """
    global _settings
    _settings = settings


def get_settings() -> Settings:
    """Return the configured Settings, built from the environment on first use."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
