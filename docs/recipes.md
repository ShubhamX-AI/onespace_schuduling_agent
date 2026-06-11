# Recipes

Worked examples for every kind of scheduling. Each is a ready-to-run `curl`
against `http://localhost:8000`. Swap the `url` for your own endpoint.

All schedules need a `name`, a trigger, and an `action`. See
[Triggers](concepts/triggers.md) and [Actions](concepts/actions.md) for the full
option set.

---

## 1. Send a reminder tomorrow at 10:00 (one-shot)

`date` trigger fires once, then the schedule goes idle.

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "reminder-user-123",
    "trigger_type": "date",
    "trigger_args": { "run_date": "2026-06-12T10:00:00" },
    "timezone": "Asia/Kolkata",
    "payload": { "user_id": 123, "template": "reminder" },
    "action": { "type": "webhook", "url": "https://email-service/send" }
  }'
```

---

## 2. Run a report every weekday at 09:00 (recurring cron)

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "daily-report",
    "trigger_type": "cron",
    "trigger_args": { "hour": 9, "minute": 0, "day_of_week": "mon-fri" },
    "timezone": "America/New_York",
    "payload": { "report": "daily" },
    "action": {
      "type": "webhook", "method": "POST",
      "url": "https://reporting-service/run",
      "headers": { "Authorization": "Bearer abc123" }
    }
  }'
```

---

## 3. Poll a service every 15 minutes (recurring interval)

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "poll-payments",
    "trigger_type": "interval",
    "trigger_args": { "minutes": 15 },
    "action": { "type": "webhook", "url": "https://billing-service/check-payments" }
  }'
```

---

## 4. Recurring, but only during a date window

`start_date` / `end_date` bound an `interval` or `cron` schedule.

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "q3-campaign",
    "trigger_type": "cron",
    "trigger_args": { "hour": 8 },
    "timezone": "Europe/London",
    "start_date": "2026-07-01T00:00:00",
    "end_date": "2026-09-30T23:59:59",
    "action": { "type": "webhook", "url": "https://campaign-service/tick" }
  }'
```

---

## 5. Call a non-POST endpoint

Set `method` and any headers your target needs.

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "nightly-cache-purge",
    "trigger_type": "cron",
    "trigger_args": { "hour": 2 },
    "action": {
      "type": "webhook", "method": "DELETE",
      "url": "https://cache-service/all",
      "headers": { "X-Api-Key": "secret" }
    }
  }'
```

---

## 6. Fire something right now (off-schedule)

Two ways:

**A — test an existing schedule immediately** (does not change its state):

```bash
curl -X POST http://localhost:8000/api/v1/schedules/665f.../run
```

**B — a true one-off** — create a `date` schedule with a `run_date` of now:

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "kickoff-now",
    "trigger_type": "date",
    "trigger_args": { "run_date": "2026-06-11T15:30:00" },
    "action": { "type": "webhook", "url": "https://worker/start" }
  }'
```

---

## 7. Make a webhook resilient (retries + timeout)

```json
"action": {
  "type": "webhook",
  "url": "https://flaky-service/run",
  "timeout_seconds": 10,
  "max_retries": 5
}
```

Five extra attempts with exponential backoff before the run is marked `error`.
See [failure handling](concepts/actions.md#failure-handling-retries-with-backoff).
Make your endpoint **idempotent** — retries can deliver the same call twice.

---

## 8. Pause and resume

```bash
curl -X POST http://localhost:8000/api/v1/schedules/665f.../pause
curl -X POST http://localhost:8000/api/v1/schedules/665f.../resume
```

Paused schedules keep their record but do not fire (`next_run_at` is `null`).

---

## 9. Change the time or payload of an existing schedule

Send only the fields that change.

```bash
curl -X PATCH http://localhost:8000/api/v1/schedules/665f... \
  -H 'Content-Type: application/json' \
  -d '{ "trigger_args": { "hour": 10 }, "payload": { "report": "daily-v2" } }'
```

The change applies on the next fire.

---

## 10. Validate before committing

Check a tricky cron/timezone first; nothing is saved.

```bash
curl -X POST http://localhost:8000/api/v1/schedules/validate \
  -H 'Content-Type: application/json' \
  -d '{ "trigger_type": "cron", "trigger_args": { "hour": 9, "day_of_week": "mon-fri" }, "timezone": "Asia/Kolkata" }'
```

---

## 11. Check whether the last run succeeded

`GET` the schedule and read its summary fields.

```bash
curl http://localhost:8000/api/v1/schedules/665f...
```

```json
{ "success": true, "message": "Schedule retrieved",
  "data": { "last_run_at": "2026-06-12T13:00:01+00:00", "last_status": "success", "last_http_status": 200, "last_error": null, "next_run_at": "2026-06-13T13:00:00+00:00" } }
```

A failed delivery shows `"last_status": "error"` with the reason in `last_error`.

---

## 12. See the full run history

Every fire is recorded — not just the latest. Newest first:

```bash
curl "http://localhost:8000/api/v1/schedules/665f.../runs?limit=20"
```

Each record has `status`, `http_status`, a truncated `response_body`, `error`,
and `started_at`/`finished_at`.

---

## 13. Get pushed a notification when it runs

Set `notify_url` and the service POSTs the result to you after every fire — no
polling. (Make the callback public; the [SSRF guard](concepts/actions.md#ssrf-protection)
blocks private hosts unless `WEBHOOK_ALLOW_PRIVATE_HOSTS=true`.)

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "nightly-sync",
    "trigger_type": "cron",
    "trigger_args": { "hour": 1 },
    "action": { "type": "webhook", "url": "https://worker/sync" },
    "notify_url": "https://my-app/scheduler-callback"
  }'
```

Your callback receives `{schedule_id, name, status, http_status, error,
started_at, finished_at}`. Delivery is best-effort — a broken callback never
fails the run itself.

---

## 12. Local testing against `localhost`

The [SSRF guard](concepts/actions.md#ssrf-protection) blocks private hosts by
default. To hit a listener on your machine during development:

```bash
export WEBHOOK_ALLOW_PRIVATE_HOSTS=true
# now an action url of http://127.0.0.1:9000/hook is allowed
```

Keep this **off** in production.
