# Errors

Errors use the same [envelope](concepts/response-envelope.md) as success
responses, with `success: false`. Check `success` first, then read `message`
(and `data` for validation issues).

## Status codes

| Status | When | `message` example |
| ------ | ---- | ----------------- |
| `400` / `422` | Invalid request body, bad trigger args, unknown timezone | `Invalid trigger_args for cron: …` |
| `404` | Schedule id not found | `Schedule '665f…' not found` |
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

See [Actions → failure handling](concepts/actions.md#failure-handling-retries-with-backoff)
for retry behavior, and the [SSRF guard](concepts/actions.md#ssrf-protection)
for why a target host might be blocked.
