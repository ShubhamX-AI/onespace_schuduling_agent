# Actions — *what* happens on fire

When a trigger fires, the service runs the schedule's **`action`**. One type
exists today: **`webhook`** — an HTTP request to a target you specify. The
schedule's **`payload`** is sent as the JSON request body, so any service in any
language can be driven by it.

```json
"action": {
  "type": "webhook",
  "method": "POST",
  "url": "https://other-service/api/run",
  "headers": { "Authorization": "Bearer abc123" },
  "timeout_seconds": 30,
  "max_retries": 3
}
```

## Field reference

| Field | Required | Default | Meaning |
| ----- | -------- | ------- | ------- |
| `type` | no | `webhook` | Action kind (only `webhook` for now). |
| `method` | no | `POST` | `GET` \| `POST` \| `PUT` \| `PATCH` \| `DELETE`. |
| `url` | **yes** | — | Target URL. Must be `http` or `https`. |
| `headers` | no | `{}` | Sent with the request (auth tokens, content negotiation, …). Names/values may not contain control characters (`\r`, `\n`, null); max 50 headers, ≤ 1024 chars each. |
| `timeout_seconds` | no | `30` | Per-attempt timeout. Range `0 < t ≤ 300`. |
| `max_retries` | no | `3` | Extra attempts after the first on failure. Range `0–10`. |

## What gets sent

```
POST <url>
Headers: <headers>
Body:    <the schedule's payload, as JSON>
```

The `payload` is the schedule field — not part of `action`. Keep transport
config in `action`; keep the data you want delivered in `payload`.

## Failure handling — retries with backoff

A response outside `2xx`, or a timeout, counts as a **failure**. The call is
retried up to `max_retries` times with exponential backoff:

```
attempt 1 ─fail─▶ wait 1s ─▶ attempt 2 ─fail─▶ wait 2s ─▶ attempt 3 ─fail─▶ wait 4s ─▶ ...
```

If every attempt fails, the run is recorded as:

```json
{ "last_status": "error", "last_error": "POST https://… failed: …" }
```

A `2xx` on any attempt marks the run `success`. Either way `last_run_at` is set.

!!! note "Make your endpoint idempotent"
    Because of retries, your endpoint may receive the same call more than once.
    Use the `payload` (e.g. an id) to de-duplicate on your side.

## SSRF protection

The service refuses to call hosts that resolve to **loopback, private,
link-local, or reserved** IPs — for example `127.0.0.1`, `10.x.x.x`,
`192.168.x.x`, and the cloud metadata address `169.254.169.254`. This stops a
schedule from being used to reach internal infrastructure.

A blocked target is recorded as an error:

```json
{ "last_status": "error", "last_error": "Blocked webhook target … (private host)" }
```

!!! warning "Local testing"
    To target a listener on `localhost` during development or testing, set
    `WEBHOOK_ALLOW_PRIVATE_HOSTS=true`. Leave it **off** in production.

## Run history

Every fire writes its own **run record** (never overwritten) to the
`schedule_runs` collection, capturing: `status` (`success`/`error`), the
webhook's `http_status`, a **truncated** `response_body` (capped by
`WEBHOOK_RESPONSE_MAX_CHARS`, default 2048), `error`, and `started_at` /
`finished_at`. Read them newest-first:

```
GET /api/v1/schedules/{id}/runs?limit=20
```

The schedule itself also keeps a quick summary of the latest run
(`last_run_at`, `last_status`, `last_error`, `last_http_status`) for a cheap
poll via `GET /schedules/{id}`.

By default records are kept forever. Set `RUN_HISTORY_TTL_DAYS` to a positive
number to auto-expire them via a MongoDB TTL index (`0` = keep forever) so
history can't grow unbounded.

## Notifications (push)

Polling is optional. Set a **`notify_url`** on the schedule and the service
**POSTs the run result there after every fire**:

```json
{
  "schedule_id": "665f…",
  "name": "daily-report",
  "status": "success",
  "http_status": 200,
  "error": null,
  "started_at": "2026-06-12T13:00:00+00:00",
  "finished_at": "2026-06-12T13:00:01+00:00"
}
```

The callback is **best-effort**: it uses the same [SSRF guard](#ssrf-protection),
a short timeout, and **no retry**. If the callback itself fails, that failure is
logged and recorded (`notified: false` on the run) — it never changes the run's
own `status`. So your action succeeding and your notification arriving are
independent outcomes.

## Coming later

The action model is shaped so new types can be added without breaking the
existing contract — e.g. `queue` or `kafka` dispatch. Today, use `webhook` and
have the receiving service forward to a queue if you need one.
