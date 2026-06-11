# OneSpace Scheduling Service

Production-grade backend for a scheduling service. Clients create schedules over
a REST API; the service stores them and fires jobs on their triggers
(interval / cron / one-shot), in any timezone, surviving restarts.

## Stack

- **FastAPI** — async HTTP API
- **MongoDB** + **Beanie 2.x** — document persistence (PyMongo native async driver)
- **APScheduler** — job scheduling with a MongoDB-backed jobstore (jobs survive restarts)
- **Granian** — Rust ASGI server for production / high-I/O (uvicorn for dev)
- **uv** — dependency & environment management

## Architecture

The request flow goes one direction — **API → service → model → MongoDB** — and
the scheduler is a side channel the service keeps in sync.

```
app/
├── main.py            # app factory + lifespan: starts/stops Mongo + scheduler
├── core/              # cross-cutting plumbing (no domain knowledge)
│   ├── config.py      #   env-driven Settings
│   ├── logging.py     #   logging setup
│   └── exceptions.py  #   error types + handlers (emit the response envelope)
├── db/mongodb.py      # AsyncMongoClient lifecycle + Beanie init + health ping
├── models/            # Beanie Documents — how data lives in MongoDB
├── schemas/           # Pydantic DTOs — the API contract (incl. ApiResponse envelope)
├── services/          # business logic; the only place that mutates DB + scheduler
├── scheduler/         # APScheduler engine + the job executor that runs on each fire
└── api/v1/            # thin routers/endpoints: parse → call service → wrap in envelope
```

**Why `models/` and `schemas/` are separate** (they look similar but aren't): a
model is the *database* shape (has `_id`, indexes); a schema is the *public API*
shape. Keeping them apart lets the DB change without breaking clients, and hides
internal fields. Endpoints never return a Document — they map it via
`ScheduleRead.from_document(...)`.

**Scheduling model**: each `Schedule` document maps 1:1 to an APScheduler job
(job id = document id). Create / update / delete / pause / resume keep the DB and
scheduler in lockstep. Triggers are timezone-aware so a schedule fires at its
intended local time regardless of the server's clock. Each run records its
outcome (`last_run_at`, `last_status`, `last_error`) back on the document. The
job executor (`app/scheduler/jobs.py`) currently does stub work (logs the firing)
— the surrounding bookkeeping is real.

## Setup

```bash
uv sync                 # install deps
cp .env.example .env     # configure (defaults target localhost Mongo)
```

## Run

With Docker (API only; reads `MONGODB_URI` and the rest from `.env`):

```bash
docker compose up --build
```

Locally for development (needs a running MongoDB), uvicorn with auto-reload:

```bash
uv run uvicorn app.main:app --reload
```

For production / high-I/O, **Granian** (Rust ASGI server, higher throughput):

```bash
uv run granian --interface asgi --host 0.0.0.0 --port 8000 --workers 4 app.main:app
```

FastAPI speaks ASGI, so Granian runs with `--interface asgi`. Scale concurrency
with `--workers`; the async endpoints make this the high-I/O path. The Docker
image already starts via Granian.

API docs at <http://localhost:8000/docs>.

## Test & lint

```bash
uv run pytest                # run tests
uv run pytest tests/test_health.py::test_health_returns_payload   # single test
uv run ruff check .          # lint
uv run ruff format .         # format
```

## API (v1)

Every response uses one envelope — payloads always live under `data`:

```json
{ "success": true, "message": "Schedule created", "data": { } }
```

Errors keep the same shape (`success: false`, `data: null`); validation errors
(422) put per-field issues in `data`:

```json
{ "success": false, "message": "Validation failed",
  "data": [{ "field": "body.name", "error": "Field required" }] }
```

| Method | Path                            | Description                       |
| ------ | ------------------------------- | --------------------------------- |
| GET    | `/api/v1/health`                | Liveness + db ping                |
| POST   | `/api/v1/schedules`             | Create schedule                   |
| POST   | `/api/v1/schedules/validate`    | Validate a trigger without saving |
| GET    | `/api/v1/schedules`             | List schedules                    |
| GET    | `/api/v1/schedules/{id}`        | Get schedule                      |
| PATCH  | `/api/v1/schedules/{id}`        | Update schedule                   |
| DELETE | `/api/v1/schedules/{id}`        | Delete schedule                   |
| POST   | `/api/v1/schedules/{id}/pause`  | Pause (stop firing, keep record)  |
| POST   | `/api/v1/schedules/{id}/resume` | Resume a paused schedule          |
| POST   | `/api/v1/schedules/{id}/run`    | Fire once immediately, off-schedule |

### Triggers

Three `trigger_type`s, each taking native APScheduler `trigger_args`:

- `interval` — `{"seconds": 30}` / `{"hours": 1}` — run every N.
- `cron` — `{"hour": 9, "minute": 0, "day_of_week": "mon-fri"}` — calendar-style.
- `date` — `{"run_date": "2026-07-01T09:00:00"}` — one-shot.

Every schedule carries a **`timezone`** (IANA, default `UTC`) so it fires at the
intended local time regardless of the host server's clock. `interval`/`cron`
schedules also accept an optional `start_date`/`end_date` active window.

Example — every weekday at 09:00 New York time, only through Q3:

```json
{
  "name": "morning-report",
  "trigger_type": "cron",
  "trigger_args": { "hour": 9, "minute": 0, "day_of_week": "mon-fri" },
  "timezone": "America/New_York",
  "start_date": "2026-07-01T00:00:00",
  "end_date": "2026-09-30T23:59:59",
  "payload": { "report": "daily" }
}
```

Responses include the live **`next_run_at`** plus the last run's outcome
(`last_run_at`, `last_status`, `last_error`), recorded automatically each fire.
