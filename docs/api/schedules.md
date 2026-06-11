# API Reference — Schedules

Base path: **`/api/v1/schedules`**. Every response uses the
[envelope](../concepts/response-envelope.md). The schedule object returned in
`data` is the [`ScheduleRead`](#the-schedule-object) shape below.

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `POST` | `/api/v1/schedules` | [Create](#create-a-schedule) |
| `POST` | `/api/v1/schedules/validate` | [Validate a trigger](#validate-a-trigger) (no save) |
| `GET` | `/api/v1/schedules` | [List](#list-schedules) |
| `GET` | `/api/v1/schedules/{id}` | [Get one](#get-a-schedule) |
| `GET` | `/api/v1/schedules/{id}/runs` | [Run history](#run-history) |
| `PATCH` | `/api/v1/schedules/{id}` | [Update](#update-a-schedule) |
| `DELETE` | `/api/v1/schedules/{id}` | [Delete](#delete-a-schedule) |
| `POST` | `/api/v1/schedules/{id}/pause` | [Pause](#pause) |
| `POST` | `/api/v1/schedules/{id}/resume` | [Resume](#resume) |
| `POST` | `/api/v1/schedules/{id}/run` | [Run now](#run-now) |

---

## The schedule object

The object you get back in `data` from every schedule endpoint:

```json
{
  "id": "665f1c2e8a4b9d0012345678",
  "name": "morning-report",
  "description": "Daily reporting kick-off",
  "trigger_type": "cron",
  "trigger_args": { "hour": 9, "minute": 0, "day_of_week": "mon-fri" },
  "timezone": "America/New_York",
  "start_date": null,
  "end_date": null,
  "payload": { "report": "daily" },
  "action": {
    "type": "webhook",
    "method": "POST",
    "url": "https://reporting-service/run",
    "headers": { "Authorization": "Bearer abc123" },
    "timeout_seconds": 30,
    "max_retries": 3
  },
  "notify_url": "https://my-app/scheduler-callback",
  "status": "active",
  "next_run_at": "2026-06-12T13:00:00+00:00",
  "last_run_at": null,
  "last_status": null,
  "last_error": null,
  "last_http_status": null,
  "created_at": "2026-06-11T15:04:05Z",
  "updated_at": "2026-06-11T15:04:05Z"
}
```

Field meanings: see [Schedules](../concepts/schedules.md).

---

## Validation rules

Request bodies are validated strictly — a violation returns a `422` envelope
with the offending field(s) in `data` (see [Errors](../errors.md)):

- **Unknown fields are rejected.** A typo like `"timezzone"` errors instead of
  being silently ignored.
- **`name`** is trimmed and must be non-blank (≤ 128 chars). On `PATCH` it can be
  changed (rename); a name already in use returns `409`.
- **`description`** is trimmed; blank becomes `null` (≤ 512 chars).
- **`timezone`** must be a resolvable IANA name (e.g. `America/New_York`).
- **`trigger_args`** must not contain the reserved keys `timezone`,
  `start_date`, or `end_date` — those are set as top-level fields.
- **`start_date`** must be before **`end_date`** when both are given.
- **`action.headers`** may not contain control characters (`\r`, `\n`, null) and
  are capped (≤ 50 headers, ≤ 1024 chars each).
- A `PATCH` with no fields is rejected.

---

## Create a schedule

`POST /api/v1/schedules` → **201**

**Request body** (see [field reference](../concepts/schedules.md#field-reference-create)):

```json
{
  "name": "morning-report",
  "trigger_type": "cron",
  "trigger_args": { "hour": 9, "minute": 0, "day_of_week": "mon-fri" },
  "timezone": "America/New_York",
  "payload": { "report": "daily" },
  "action": {
    "type": "webhook",
    "method": "POST",
    "url": "https://reporting-service/run",
    "headers": { "Authorization": "Bearer abc123" }
  },
  "notify_url": "https://my-app/scheduler-callback"
}
```

`notify_url` is optional — when set, the run result is POSTed there after each
fire (see [notifications](../concepts/actions.md#notifications-push)).

**Response** — `message: "Schedule created"`, `data` = the schedule object.

Errors: `409` if `name` already exists; `422` for invalid body or bad trigger args.

---

## Validate a trigger

`POST /api/v1/schedules/validate` → **200**

Check a trigger spec (including timezone) **without** persisting anything.

**Request body:**

```json
{ "trigger_type": "cron", "trigger_args": { "hour": 9 }, "timezone": "Asia/Kolkata" }
```

**Valid:**

```json
{ "success": true, "message": "Trigger is valid", "data": null }
```

**Invalid** (still HTTP 200 — read `success`):

```json
{ "success": false, "message": "Unknown timezone 'Mars/Phobos'", "data": null }
```

---

## List schedules

`GET /api/v1/schedules` → **200**

`message: "Schedules retrieved"`, `data` = array of schedule objects (each with a
live `next_run_at`).

---

## Get a schedule

`GET /api/v1/schedules/{id}` → **200**

`message: "Schedule retrieved"`, `data` = the schedule object. `404` if unknown.

---

## Run history

`GET /api/v1/schedules/{id}/runs` → **200**

Recent run outcomes, newest first. Query param `limit` (default 20, max 100).
`message: "Runs retrieved"`, `data` = array of run objects:

```json
{
  "id": "6660aa…",
  "schedule_id": "665f1c2e8a4b9d0012345678",
  "status": "error",
  "http_status": 500,
  "response_body": "{\"detail\":\"boom\"}",
  "error": "POST https://… failed: Server error '500 …'",
  "started_at": "2026-06-12T13:00:00+00:00",
  "finished_at": "2026-06-12T13:00:04+00:00",
  "notified": true
}
```

`response_body` is truncated to `WEBHOOK_RESPONSE_MAX_CHARS`. `404` for an
unknown/malformed id. See [run history & notifications](../concepts/actions.md#run-history).

---

## Update a schedule

`PATCH /api/v1/schedules/{id}` → **200**

Send **only the fields you want to change** — all are optional, but the body
must contain **at least one** field (an empty `{}` returns `422`). Updatable:
`name`, `description`, `trigger_type`, `trigger_args`, `timezone`, `start_date`,
`end_date`, `payload`, `action`, `notify_url`, `status`.

```json
{ "trigger_args": { "hour": 10 }, "payload": { "report": "daily-v2" } }
```

`name` can be changed (rename); renaming to a name already in use returns `409`.
All [validation rules](#validation-rules) apply to the fields you send.

`message: "Schedule updated"`, `data` = the updated object. The scheduler is
re-synced atomically — a bad trigger leaves the stored schedule unchanged (`422`).

!!! note
    Editing `payload` or `action` takes effect on the **next** fire — the
    executor always reads the latest stored schedule.

---

## Delete a schedule

`DELETE /api/v1/schedules/{id}` → **200**

Removes the schedule and its scheduler job.

```json
{ "success": true, "message": "Schedule deleted", "data": null }
```

---

## Pause

`POST /api/v1/schedules/{id}/pause` → **200**

Stops firing but keeps the record. `status` becomes `paused`, `next_run_at`
becomes `null`. `message: "Schedule paused"`.

## Resume

`POST /api/v1/schedules/{id}/resume` → **200**

Re-arms a paused schedule. `status` becomes `active` and `next_run_at` is
populated again. `message: "Schedule resumed"`.

## Run now

`POST /api/v1/schedules/{id}/run` → **200**

Fires the action **once, immediately**, independent of the trigger and without
changing `status`. Useful for testing the webhook or forcing an off-cycle run.
`message: "Schedule triggered"`. The run's outcome is recorded in
`last_run_at` / `last_status` / `last_error` like any scheduled fire.
