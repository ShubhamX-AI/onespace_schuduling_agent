# Schedules

A **schedule** is the unit you create, read, update, and delete. It bundles
*when* to fire (trigger), *what* to do (action), and *what data* to send
(payload), plus its lifecycle state.

## Anatomy

```json
{
  "name": "morning-report",
  "description": "Daily reporting kick-off",
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

## Field reference (create)

| Field | Required | Default | Notes |
| ----- | -------- | ------- | ----- |
| `name` | **yes** | — | 1–128 chars. **Unique** across all schedules. |
| `description` | no | `null` | Up to 512 chars. |
| `trigger_type` | **yes** | — | `date` \| `interval` \| `cron`. See [Triggers](triggers.md). |
| `trigger_args` | no | `{}` | Native APScheduler args for the trigger type. |
| `timezone` | no | `"UTC"` | IANA name, e.g. `Asia/Kolkata`. |
| `start_date` | no | `null` | Active-window start (`interval`/`cron` only). |
| `end_date` | no | `null` | Active-window end (`interval`/`cron` only). |
| `payload` | no | `{}` | Sent as the webhook JSON body. |
| `action` | **yes** | — | What to fire. See [Actions](actions.md). |
| `notify_url` | no | `null` | Callback POSTed with each run's result. See [notifications](actions.md#notifications-push). |

## Read-only fields (returned, never sent)

These appear in every schedule response and are managed by the service:

| Field | Meaning |
| ----- | ------- |
| `id` | The schedule's id (also the scheduler job id). |
| `next_run_at` | Live next fire time, read from the scheduler. `null` if paused/expired. |
| `last_run_at` | When it last fired. `null` until the first run. |
| `last_status` | Outcome of the last run: `success` or `error`. |
| `last_error` | Error message from the last failed run, else `null`. |
| `last_http_status` | HTTP status the webhook returned on the last run, else `null`. |
| `status` | `active` (armed) or `paused` (kept, not firing). |
| `created_at` / `updated_at` | Timestamps (UTC). |

## Lifecycle

```
create ──▶ active ──(pause)──▶ paused ──(resume)──▶ active ──(delete)──▶ gone
                │                                       │
                └────────── fires on trigger ──────────┘
                            (records last_run_* )
```

- **active** — armed; fires on its trigger and records each outcome.
- **paused** — the record is kept but the scheduler job is removed, so it does
  not fire. `next_run_at` becomes `null`. Resume to re-arm.
- **run now** — fire once immediately, off-schedule, without changing state.

See the [API Reference](../api/schedules.md) for the endpoints behind each transition.

## Why models and the API contract differ

Internally the database document has more plumbing (Mongo `_id`, indexes) than
the API exposes. The service always maps the stored document to a clean response
shape, so the database can change without breaking your integration. You only
ever see the fields documented above.
