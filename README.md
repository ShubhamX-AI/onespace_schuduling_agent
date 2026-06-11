# OneSpace Scheduling Service

Production-grade backend for a scheduling service. Clients create schedules over
a REST API; the service stores them and, on each trigger (interval / cron /
one-shot), fires the schedule's **action** — today, an outbound webhook (HTTP
call) to any other service. Fires in any timezone and survives restarts.

Think of it as a programmable alarm clock for your other services: *"at this
time, call this URL with this payload."* The scheduler keeps time and delivers
the call; the work itself belongs to whatever service receives it.

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
outcome (`last_run_at`, `last_status`, `last_error`) back on the document. On
fire, the job executor (`app/scheduler/jobs.py`) reloads the schedule and runs
its action via `app/scheduler/actions.py` — for a webhook, an HTTP call hardened
against SSRF and retried with backoff.

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

API docs at <http://localhost:8000/docs> (Swagger / OpenAPI).

## Documentation site

A full usage guide (concepts, every endpoint with payloads + responses, and
recipes for every scheduling pattern) is built with **MkDocs Material** from
`docs/` and served by the app at **`/documentation`**.

```bash
uv sync --group docs                 # install docs toolchain (once)
uv run mkdocs serve                  # live preview at http://localhost:8000 (docs only)
uv run mkdocs build --strict         # build into ./site
```

Once `./site` exists, the running API serves it at
<http://localhost:8000/documentation>. The Docker image builds and bundles it
automatically. If `./site` is absent, the route is simply not mounted (the API
still runs).

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
  "payload": { "report": "daily" },
  "action": {
    "type": "webhook",
    "method": "POST",
    "url": "https://reporting-service/run",
    "headers": { "Authorization": "Bearer abc123" }
  }
}
```

Common timings, all the same `trigger_type`s:

| You want…              | trigger_type | trigger_args                          |
| ---------------------- | ------------ | ------------------------------------- |
| Immediately / one-off  | `date`       | `{"run_date": "<now or future ISO>"}` (or call `/{id}/run`) |
| After one day          | `date`       | `{"run_date": "2026-06-12T10:00:00"}` |
| Every N seconds/hours  | `interval`   | `{"hours": 1}`                        |
| Every day at a time    | `cron`       | `{"hour": 9, "minute": 0}`            |

### Actions — what fires

When a schedule triggers, the service runs its **`action`**. One type today:
`webhook`, an HTTP request to a target service. The schedule's **`payload`** is
sent as the JSON request body, so any service in any language can be driven by it.

| Field             | Required | Default | Meaning                                          |
| ----------------- | -------- | ------- | ------------------------------------------------ |
| `type`            | no       | `webhook` | Action kind (only `webhook` for now).          |
| `method`          | no       | `POST`  | HTTP method (`GET`/`POST`/`PUT`/`PATCH`/`DELETE`). |
| `url`             | **yes**  | —       | Target URL (`http`/`https`).                     |
| `headers`         | no       | `{}`    | Headers sent with the call (auth tokens, etc.).  |
| `timeout_seconds` | no       | `30`    | Per-attempt timeout (`0 < t ≤ 300`).             |
| `max_retries`     | no       | `3`     | Extra attempts after the first on failure (`0–10`). |

**Failure handling.** A non-2xx response or timeout is a failure. The call is
retried up to `max_retries` times with exponential backoff (1s, 2s, 4s, …); if
all attempts fail, the run is recorded with `last_status: "error"` and the
reason in `last_error`.

**SSRF protection.** Target hosts that resolve to loopback, private, link-local,
or reserved IPs (e.g. `127.0.0.1`, `10.x`, the cloud metadata `169.254.169.254`)
are blocked. To target a local listener in dev/test, set
`WEBHOOK_ALLOW_PRIVATE_HOSTS=true`.

Responses include the live **`next_run_at`** plus the last run's outcome
(`last_run_at`, `last_status`, `last_error`), recorded automatically each fire.
