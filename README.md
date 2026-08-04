# OneSpace Scheduling Service

Production-grade backend for a scheduling service. Clients create schedules over
a REST API; the service stores them and, on each trigger (interval / cron /
one-shot), fires the schedule's **action** — today, an outbound webhook (HTTP
call) to any other service. Fires in any timezone and survives restarts.

Think of it as a programmable alarm clock for your other services: *"at this
time, call this URL with this payload."* The scheduler keeps time and delivers
the call; the work itself belongs to whatever service receives it.

**Core model.** A `Schedule` document maps 1:1 to an APScheduler job (job id =
document id). Create / update / delete / pause / resume keep the DB and scheduler
in lockstep. Triggers are timezone-aware so a schedule fires at its intended
local time regardless of the server's clock. Each run records its outcome
(`last_run_at`, `last_status`, `last_error`) back on the document. On fire, the
job executor (`src/scheduling/jobs.py`) reloads the schedule and runs its action
via `src/scheduling/actions.py` — for a webhook, an HTTP call hardened against
SSRF and retried with backoff.

## Response envelope

Every endpoint returns the same shape — payloads always live under `data`:

```json
{ "success": true, "message": "Schedule created", "data": { } }
```

Errors keep the same shape (`success: false`, `data: null`); validation errors
(422) put per-field issues in `data`:

```json
{ "success": false, "message": "Validation failed",
  "data": [{ "field": "body.name", "error": "Field required" }] }
```

## Requirements

- **Python 3.12+**
- **MongoDB** — the only required external service (persistence + jobstore)
- **uv** — dependency & environment management
- Optional: the **docs** dependency group to build the MkDocs documentation site

## Installation

```bash
uv sync                 # install deps
cp .env.example .env     # configure (defaults target localhost Mongo)
```

**Locally for development** (needs a running MongoDB), uvicorn with auto-reload:

```bash
uv run uvicorn server:app --reload
```

**Production / high-I/O** — run the same entrypoint the image uses, **Granian**
(Rust ASGI server):

```bash
PORT=3011 WORKERS=4 python server_run.py
# equivalently, the raw command it execs:
uv run granian --interface asgi --host 0.0.0.0 --port 3011 --workers 4 server:app
```

FastAPI speaks ASGI, so Granian runs with `--interface asgi`. Scale concurrency
with `WORKERS`; the async endpoints make this the high-I/O path.

**With Docker** (reads `MONGODB_URI`, `PORT`, and the rest from `.env`):

```bash
docker compose up --build
```

API docs at `http://localhost:$PORT/docs` (Swagger / OpenAPI) — e.g.
<http://localhost:3011/docs>.

**Test & lint:**

```bash
uv run pytest                # run tests
uv run ruff check .          # lint
uv run ruff format .         # format
```

## Environment

All configuration is read from environment / `.env` by `src/core/config.py` —
never via scattered `os.getenv` calls.

| Variable | Default | Note |
| -------- | ------- | ---- |
| `APP_NAME` | `OneSpace Scheduling Service` | App title shown in OpenAPI docs |
| `APP_ENV` | `development` | `development` / `production` |
| `DEBUG` | `false` | FastAPI debug mode |
| `LOG_LEVEL` | `INFO` | Log level |
| `API_V1_PREFIX` | `/api/v1` | URL prefix for v1 routes |
| `HOST` | `0.0.0.0` | Bind host (reserved — `server_run.py` binds `0.0.0.0`) |
| `PORT` | `3011` | Bind port (read by `server_run.py` / docker-compose) |
| `WORKERS` | `1` | Granian worker processes |
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB` | `onespace_scheduler_scheduling` | Database name |
| `SCHEDULER_JOBS_COLLECTION` | `onespace_scheduler_jobs` | APScheduler jobstore collection |
| `SCHEDULER_TIMEZONE` | `UTC` | Scheduler default timezone |
| `WEBHOOK_ALLOW_PRIVATE_HOSTS` | `false` | Allow webhook targets on loopback/private IPs (SSRF guard; enable only for dev/test) |
| `WEBHOOK_RESPONSE_MAX_CHARS` | `2048` | Max chars of a webhook response body kept in each run record |
| `NOTIFY_TIMEOUT_SECONDS` | `10` | Timeout for the best-effort notify callback |
| `RUN_HISTORY_TTL_DAYS` | `0` | Days to keep run history (TTL); `0` = keep forever |
| `DOCS_SITE_DIR` | `site` | Built MkDocs site, served at `/documentation` (route not mounted if absent) |

## Endpoints

**Ownership.** Every schedule endpoint (except `/validate`) requires an
**`X-Owner-Id`** header; schedules are scoped to that owner, so callers only see
and control their own (another owner's id returns `404`, a missing header `401`).
Names are unique *per owner*. This is tenant partitioning, not authentication —
the header is trusted as-is, so front it with an authenticating gateway in
production. See [docs/concepts/schedules.md](docs/concepts/schedules.md#ownership).

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

Request bodies are validated strictly: unknown fields are rejected, `name` is
trimmed/non-blank (renamable via `PATCH`, unique per owner), `timezone` must be a valid
IANA name, `trigger_args` can't carry the reserved `timezone`/`start_date`/`end_date`
keys, `start_date` must precede `end_date`, and webhook `headers` reject control
characters. Full list: [docs/api/schedules.md](docs/api/schedules.md#validation-rules).

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
(`last_run_at`, `last_status`, `last_error`, `last_http_status`), recorded
automatically each fire.

### Run history & notifications

Every fire writes a record (status, HTTP code, truncated response body,
timestamps) to the `onespace_scheduler_schedule_runs` collection — read newest-first via
`GET /api/v1/schedules/{id}/runs`. Set a schedule's **`notify_url`** and the
service POSTs each run's result there (best-effort, SSRF-guarded, no retry), so
the creator is pushed an outcome instead of polling. History retention is
bounded by `RUN_HISTORY_TTL_DAYS` (`0` = keep forever).

## Project Structure

Request flow is one direction — **API → service → model → MongoDB** — and the
scheduler is a side channel the service keeps in sync. Layering is enforced:
`core/` and `scheduling/` never import `api/`.

```
server.py                   # app entry: factory + lifespan + exception handlers + docs mount
server_run.py               # production runner: execs Granian with server:app
src/
├── api/                    # HTTP surface — thin routes, no business logic
│   ├── models/             #   Pydantic DTOs — the API contract (response envelope + schedule)
│   └── routes/v1/          #   endpoints + shared deps (_common.py: X-Owner-Id)
├── core/                   # cross-cutting plumbing, depends on nothing domain-specific
│   ├── config.py           #   Settings (pydantic-settings, env-driven) + get_settings()
│   ├── exceptions.py       #   AppError hierarchy + handlers that emit the envelope
│   ├── db/                 #   db_connect.py (lifecycle) + db_schema.py (Beanie Documents)
│   └── logging/logger.py   #   logging setup + get_logger()
└── scheduling/             # domain: business logic + the APScheduler engine
    ├── schedule_service.py #   keeps DB and scheduler in sync
    ├── scheduler.py        #   AsyncIOScheduler + MongoDB jobstore
    ├── jobs.py             #   job executor (fires a schedule's action)
    └── actions.py          #   webhook action runner + notify callback
tests/                      # pytest suite, mirrors src/ layout
docs/                       # MkDocs usage guide, built and served at /documentation
```

**Why `models/` (DB) and `schemas`-style DTOs are separate:** `src/core/db/db_schema.py`
holds the Beanie *Documents* — the DB shape (`_id`, indexes); `src/api/models/`
holds the public API DTOs. Endpoints never return a Document — they map it via
`ScheduleRead.from_document(...)` so the DB can change without breaking clients.

## Data stores

All data lives in the `onespace_scheduler_scheduling` MongoDB database.

| Collection | What it holds | Keyed by |
| ---------- | ------------- | -------- |
| `onespace_scheduler_schedules` | Schedule documents (the persisted definition of each scheduled job) | `(owner_id, name)` unique index; `status` index |
| `onespace_scheduler_schedule_runs` | One record per fire — status, HTTP code, truncated response body, timestamps | `(schedule_id, finished_at)` index, newest-first; optional TTL on `finished_at` |
| `onespace_scheduler_jobs` | APScheduler's MongoDB jobstore — jobs survive restarts | job id == schedule document id |

## Stack

| Layer | Technology |
| ----- | ---------- |
| API | FastAPI (async) |
| Persistence | MongoDB via Beanie 2.x ODM (PyMongo native async driver) |
| Scheduling | APScheduler (AsyncIOScheduler + MongoDB jobstore) |
| Server | Granian (prod) / uvicorn (dev) |
| Env & deps | uv |
| Docs | MkDocs Material |

## Deployment

`deploy.sh` does a one-shot deploy on a host that has Docker + a populated
`.env`:

```bash
./deploy.sh        # git pull → docker compose up -d --build → docker system prune
```

Env knobs that matter for serving: `PORT` (bind port, default 3011) and
`WORKERS` (Granian processes). Everything else is in `.env.example`.

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
`http://localhost:$PORT/documentation` (e.g. <http://localhost:3011/documentation>).
The Docker image builds and bundles it
automatically. If `./site` is absent, the route is simply not mounted (the API
still runs).

## Licence

Copyright (c) 2026 Indus Net Technologies Private Limited.

OneSpace is licensed under the [Business Source License 1.1 (BUSL-1.1)](LICENSE).

You may use, copy, modify, and distribute this software for your own internal
business purposes. Commercial use, redistribution, white-labelling, or hosting
this software as a service for third parties requires a separate commercial
licence from INT.

For licensing enquiries: licensing@intglobal.com
