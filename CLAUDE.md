# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`onespace-schuduling-agent` — a production-grade backend for a **scheduling service**. Clients create schedules over a REST API; the service persists them and fires jobs on their triggers (interval / cron / one-shot), in any timezone, surviving restarts.

Stack: **FastAPI** (async API) · **MongoDB** via **Beanie 2.x ODM** (PyMongo native async driver — *not* Motor) · **APScheduler** (AsyncIOScheduler + MongoDB jobstore) · **uv** (deps) · **Granian** (prod ASGI server) / **uvicorn** (dev).

## Commands

```bash
uv sync                      # install/lock deps
cp .env.example .env          # configure (MONGODB_URI etc.)

# Run
uv run uvicorn server:app --reload                                   # dev (auto-reload)
uv run granian --interface asgi --host 0.0.0.0 --port 8000 server:app # prod / high-I/O
docker compose up --build                                              # api + mongo

# Quality gates — run all three before calling work done
uv run ruff check .                                  # lint
uv run ruff format .                                 # format
uv run pytest -q                                     # all tests
uv run pytest tests/scheduling/test_triggers.py::test_interval_trigger_builds   # single test
```

## Architecture

Request flow is one direction: **API → service → model → MongoDB**. The scheduler is a side channel the service keeps in sync.

```
server.py            # app entry: factory + lifespan + exception handlers + docs mount
server_run.py        # production runner: execs Granian with server:app
src/
├── api/             # HTTP surface — thin routes, no business logic
│   ├── models/      #   Pydantic DTOs — the API contract (response envelope + schedule)
│   ├── routes/health.py  # GET /health — deep probe, unprefixed, always 200
│   └── routes/v1/   #   endpoints + shared deps (_common.py: X-Owner-Id)
├── core/            # cross-cutting plumbing, depends on nothing domain-specific
│   ├── config.py    #   Settings (pydantic-settings, env-driven) + get_settings()
│   ├── exceptions.py#   AppError hierarchy + handlers that emit the envelope
│   ├── db/          #   db_connect.py (lifecycle) + db_schema.py (Beanie Documents)
│   └── logging/logger.py   # logging setup + get_logger()
└── scheduling/      # domain: business logic + the APScheduler engine
    ├── schedule_service.py  # ownership, name uniqueness, reads
    ├── lifecycle.py         # every status transition + its APScheduler job (incl. auto-pause, run-now)
    ├── triggers.py          # build_trigger: timezone-aware APScheduler triggers
    ├── scheduler.py         # AsyncIOScheduler + MongoDB jobstore
    ├── jobs.py              # the Run module: one fire, load to recorded outcome
    └── actions.py           # webhook action runner + notify callback
```

### Rules that keep it clean

- **Layer direction**: inner layers never import outer ones. `core/` and `scheduling/` know nothing about `api/`. Business rules live in `src/scheduling/`, never in endpoints.
- **models vs schemas are deliberately separate** — `src/core/db/db_schema.py` Documents are the DB shape (has `_id`, indexes); `src/api/models/` DTOs are the public API shape. Never return a Document directly; map it with `ScheduleRead.from_document(...)`. This lets the DB change without breaking clients.
- **Ownership (multi-tenant)**: every schedule has an `owner_id`. Endpoints (except `/validate`) require an `X-Owner-Id` header → `src/api/routes/v1/_common.py:current_owner` (missing/blank = 401 `AuthError`). The service scopes *every* query by `owner_id`: `get_schedule(id, owner_id)` 404s on a mismatch (no existence leak), `name` is unique per `(owner_id, name)`. It's trust-on-header partitioning, **not** auth — an upstream gateway is assumed to set the header.
- **One schedule = one APScheduler job**, job id == document id. `src/scheduling/lifecycle.py` is the only module that arms or disarms jobs. On a failed step the schedule ends in the state that does not fire: disarm then save (startup `resync_jobs` repairs a failed save), save then arm (a failed arm reverts the DB change). Writes are partial (`$set`/`$inc`), never a full-document save. Resume resets `consecutive_errors`. A job is re-armed only when trigger fields or status change, and never armed without a future fire (422 instead). Run-now is a separate one-off job `run-now:<id>`.
- **Triggers** are timezone-aware: `build_trigger()` injects the schedule's IANA `timezone` (and optional start/end window) into the APScheduler trigger, so firing is independent of the host clock.
- **Actions** are what a schedule *does* on fire (the WHEN is the trigger; the WHAT is the action). One type today — `webhook` (`src/core/db/db_schema.py:WebhookAction`): the schedule's `payload` is sent as the HTTP body. The action model is shaped for future types (`queue`, `kafka`) without breaking the contract. Execution lives in `src/scheduling/actions.py:run_action` — SSRF-guarded (private/loopback hosts blocked unless `WEBHOOK_ALLOW_PRIVATE_HOSTS=true`) and retried with exponential backoff up to `max_retries`.
- **Run outcomes** are self-recorded: `src/scheduling/jobs.py:execute_schedule` takes only the schedule id, reloads the document (DB is the source of truth — no payload in jobstore kwargs), runs the action (`actions.run_action` never raises; failure is `result.error`), `$set`s only the run-summary fields, then asks `lifecycle.pause_if_failing` to atomically auto-pause at `consecutive_error_threshold`. Notify and the `ScheduleRun` insert come after, best-effort, so they can never lose the error count.
- **Run history + notify**: each fire also inserts a `ScheduleRun` document (`onespace_scheduler_schedule_runs`, TTL-bounded by `run_history_ttl_days`) capturing status + HTTP code + truncated response body; read via `GET /schedules/{id}/runs`. If the schedule has a `notify_url`, `src/scheduling/actions.py:notify` POSTs the result there — best-effort (SSRF-guarded, no retry, failures only logged, never fail the run).

### Response envelope (every endpoint)

All responses use one shape via `src/api/models/response_schemas.py:ApiResponse[T]`:

```json
{ "success": true, "message": "...", "data": <payload or null> }
```

Errors use the same shape through the handlers in `core/exceptions.py` (422 validation errors put per-field issues in `data`). When adding an endpoint, return `ApiResponse[...]` and set `response_model` accordingly — don't return raw models or dicts.

## Conventions

- Beanie 2.x uses PyMongo's `AsyncMongoClient`; do **not** add `motor`.
- Async all the way down — endpoints, service, DB calls, job executor.
- `ApiResponse[T]` uses PEP 695 generics (`class ApiResponse[T]`) — requires Python 3.12.
- New work should follow the `senior-engineer` skill: understand → plan with todos → execute → simplicity pass (a junior should be able to read the result).
