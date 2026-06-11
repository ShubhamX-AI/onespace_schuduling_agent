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
uv run uvicorn app.main:app --reload                                   # dev (auto-reload)
uv run granian --interface asgi --host 0.0.0.0 --port 8000 app.main:app # prod / high-I/O
docker compose up --build                                              # api + mongo

# Quality gates — run all three before calling work done
uv run ruff check .                                  # lint
uv run ruff format .                                 # format
uv run pytest -q                                     # all tests
uv run pytest tests/test_trigger.py::test_interval_trigger_builds   # single test
```

## Architecture

Request flow is one direction: **API → service → model → MongoDB**. The scheduler is a side channel the service keeps in sync.

```
app/
├── main.py            # app factory + lifespan: starts/stops Mongo + scheduler
├── core/              # cross-cutting plumbing, depends on nothing domain-specific
│   ├── config.py      #   Settings (pydantic-settings, env-driven) + get_settings()
│   ├── logging.py     #   logging config
│   └── exceptions.py  #   AppError hierarchy + handlers that emit the envelope
├── db/mongodb.py      # AsyncMongoClient lifecycle + init_beanie + ping
├── models/            # Beanie Documents — how data lives in MongoDB
├── schemas/           # Pydantic DTOs — the API contract (in/out), incl. ApiResponse
├── services/          # business logic; the ONLY place that mutates models + scheduler
├── scheduler/         # APScheduler engine (scheduler.py) + job executor (jobs.py)
└── api/v1/            # routers + endpoints (thin: parse → call service → wrap)
```

### Rules that keep it clean

- **Layer direction**: inner layers never import outer ones. `core/` and `scheduler/` know nothing about `api/`. Business rules live in `services/`, never in endpoints.
- **models vs schemas are deliberately separate** — a `models/` Document is the DB shape (has `_id`, indexes); a `schemas/` DTO is the public API shape. Never return a Document directly; map it with `ScheduleRead.from_document(...)`. This lets the DB change without breaking clients.
- **One schedule = one APScheduler job**, job id == document id. `services/schedule_service.py` keeps DB and scheduler consistent: on a scheduler failure it rolls back / leaves the DB untouched (see `create_schedule`, `update_schedule`).
- **Triggers** are timezone-aware: `build_trigger()` injects the schedule's IANA `timezone` (and optional start/end window) into the APScheduler trigger, so firing is independent of the host clock.
- **Run outcomes** are self-recorded: `scheduler/jobs.py:execute_schedule` is async, runs the work, and writes `last_run_at/last_status/last_error` back to the document.

### Response envelope (every endpoint)

All responses use one shape via `app/schemas/response.py:ApiResponse[T]`:

```json
{ "success": true, "message": "...", "data": <payload or null> }
```

Errors use the same shape through the handlers in `core/exceptions.py` (422 validation errors put per-field issues in `data`). When adding an endpoint, return `ApiResponse[...]` and set `response_model` accordingly — don't return raw models or dicts.

## Conventions

- Beanie 2.x uses PyMongo's `AsyncMongoClient`; do **not** add `motor`.
- Async all the way down — endpoints, service, DB calls, job executor.
- `ApiResponse[T]` uses PEP 695 generics (`class ApiResponse[T]`) — requires Python 3.12.
- New work should follow the `senior-engineer` skill: understand → plan with todos → execute → simplicity pass (a junior should be able to read the result).
