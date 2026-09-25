# Research — 2026-09-25-security-api-logging

## Attack surface

| Entry point | Auth | Input schema | Sinks |
|-------------|------|--------------|-------|
| `POST /api/v1/schedules` | `X-Owner-Id` (trusted header) | `ScheduleCreate` (extra=forbid) | MongoDB insert, APScheduler job, later outbound HTTP (webhook url, notify_url) |
| `POST /api/v1/schedules/validate` | none | `TriggerSpec` | APScheduler trigger construction (CPU only) |
| `GET /api/v1/schedules` | header | none | MongoDB find by owner, unbounded |
| `GET /api/v1/schedules/{id}` | header | path str | MongoDB get + owner compare |
| `GET /api/v1/schedules/{id}/runs` | header | `limit` 1..100 | MongoDB find |
| `PATCH /api/v1/schedules/{id}` | header | `ScheduleUpdate` (extra=forbid) | MongoDB `$set`, job re-arm |
| `DELETE /api/v1/schedules/{id}` | header | path | MongoDB delete, job remove |
| `POST .../{id}/pause`, `/resume`, `/run` | header | path | status change, one-off job |
| `GET /health` | none | none | Mongo ping, scheduler state; returns exception text |
| `/documentation/*` | none | path | StaticFiles (site/) |
| `/docs`, `/redoc`, `/openapi.json` | none | none | FastAPI defaults, always on |
| Scheduler fire `execute_schedule` | internal | schedule id | outbound HTTP (webhook, notify), logs, run history |

Trust boundaries: HTTP request -> DTO -> Mongo; stored `action.url` / `notify_url` -> outbound HTTP (SSRF); upstream response body -> Mongo -> `GET /runs` (read-back channel); exception text -> logs / `last_error` / `/health`.

## Scanner results

| Tool | Version | Command | Hits |
|------|---------|---------|------|
| ruff | 0.16.9 | `uvx ruff check --select S,BLE,ASYNC --output-format concise src server.py server_run.py` | 4 |
| semgrep | 1.178.0 | `uvx semgrep scan --metrics=off --config p/python --config p/owasp-top-ten --config p/secrets src server.py server_run.py` | 1 |
| pip-audit | 2.10.1 | `uv export --no-dev --no-hashes` then `uvx pip-audit -r req.txt --disable-pip --no-deps` | 7 (3 packages) |
| gitleaks | - | not installed | not run |

### Triage

| Hit | Location | Verdict | Reason |
|-----|----------|---------|--------|
| S104 bind all interfaces | `server_run.py:19` | false positive | container bind; exposure concern covered by S-001 |
| S104 bind all interfaces | `src/core/config.py:29` | false positive | same; value unused by `server_run.py` |
| S606 process without shell | `server_run.py:28` | false positive | argv list, no shell, env set by operator |
| BLE001 blind except | `src/api/routes/health.py:47` | false positive | deliberate: probe must never 500 |
| semgrep dangerous-os-exec-tainted-env-args | `server_run.py:28` | false positive | `PORT`/`WORKERS` operator env passed as argv, no shell |
| starlette 1.2.1 PYSEC-2026-248 (request.url authority confusion) | `uv.lock` | confirmed, low reachability | app never reads `request.url`; StaticFiles dir redirect uses `URL(scope=...)` but only for paths routed under `/documentation` |
| starlette 1.2.1 PYSEC-2026-249 (urlencoded form limits ignored) | `uv.lock` | not reachable | no `request.form()` / `Form` in app |
| anyio 4.13.0 CVE-2026-63374 (IDNA TLS) | `uv.lock` | low reachability | outbound httpx TLS to IDN host, needs traffic hijack |
| anyio 4.13.0 CVE-2026-64847 (process-pool stderr) | `uv.lock` | not reachable | no anyio process pool |
| pydantic-settings 2.14.1 CVE-2026-58203 (secrets_dir symlink) | `uv.lock` | not reachable | no `secrets_dir` configured |

## Runtime facts checked

- Python 3.12.3: `ipaddress` flags `::ffff:127.0.0.1`, `::ffff:10.0.0.1`, `::ffff:169.254.169.254`, `0.0.0.0` as blocked. `100.64.0.1` (CGNAT, `is_global=False`) and `224.0.0.1` (multicast) pass the guard in `actions.py:140`.
- httpx `AsyncClient(follow_redirects=False)` default: redirects not followed.
- Starlette `ServerErrorMiddleware.__call__`: `if self.debug: response = self.debug_response(...)` runs before the installed 500 handler.
- `armable_trigger(TriggerSpec(trigger_type="interval", trigger_args={"seconds": 0.01}))` returns `interval[0:00:00.010000]`.
- fastapi 0.136.3 in lock.

## Files reviewed (lines)

`server.py` 69, `server_run.py` 32, `src/api/routes/v1/_common.py` 22, `router.py` 13, `schedules.py` 114, `src/api/routes/health.py` 77, `src/api/models/schedule.py` 164, `response_schemas.py` 25, `src/core/exceptions.py` 94, `config.py` 86, `logging/logger.py` 39, `db/db_connect.py` 60, `db/db_schema.py` 166, `src/scheduling/actions.py` 141, `jobs.py` 89, `schedule_service.py` 107, `triggers.py` 132, log call sites in `scheduler.py`, `lifecycle.py`; `Dockerfile`, `docker-compose.yml`, `.env.example`.
