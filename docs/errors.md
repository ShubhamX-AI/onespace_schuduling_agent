# Errors

Errors use the same [envelope](concepts/response-envelope.md) as success
responses, with `success: false`. Check `success` first, then read `message`
(and `data` for validation issues).

## Status codes

| Status | When | `message` example |
| ------ | ---- | ----------------- |
| `422` | Invalid request body, bad trigger args, unknown timezone | `Invalid trigger_args for cron: …` |
| `401` | Missing/blank `X-Owner-Id` header (every endpoint except `/validate`) | `Missing X-Owner-Id header` |
| `404` | Schedule id not found, or owned by someone else | `Schedule '665f…' not found` |
| `409` | A schedule with that `name` already exists | `Schedule 'morning-report' already exists` |
| `500` | Unexpected server error | `Internal server error` |

## Validation errors (422)

When the request body fails validation, `data` is an array of per-field issues:

```json
{
  "success": false,
  "message": "Validation failed",
  "data": [
    { "field": "body.name", "error": "Field required" },
    { "field": "body.action.url", "error": "Field required" }
  ]
}
```

`field` is the dotted path into the request body, so nested action/trigger
problems point at the exact key.

## Run failures vs request failures

Two different things — don't confuse them:

- **Request failure** — your call to *this* API was rejected (the cases above).
  You get a `success: false` response immediately.
- **Run failure** — the schedule was created fine, but later its **webhook**
  call failed. That is **not** an API error; it is recorded on the schedule as
  `last_status: "error"` with `last_error`. Read it via
  `GET /api/v1/schedules/{id}`.

Schedules that accumulate too many consecutive errors (default threshold: 50) are
automatically **paused** to prevent continuous failed requests. The consecutive
error count is tracked in the `consecutive_errors` field and can be monitored.
When the threshold is reached, the schedule status changes to `paused` and the
scheduler job is removed.

See [Actions → failure handling](concepts/actions.md#failure-handling-retries-with-backoff)
for retry behavior, and the [SSRF guard](concepts/actions.md#ssrf-protection)
for why a target host might be blocked.
