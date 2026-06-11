# Response envelope

**Every** response — success or error — has the same three-field shape. Real
payloads always live under `data`; `message` explains the outcome.

```json
{
  "success": true,
  "message": "Schedule created",
  "data": { "...": "..." }
}
```

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `success` | bool | `true` on success, `false` on error. |
| `message` | string | Human-readable summary of what happened. |
| `data` | object / array / `null` | The payload, or `null` when there is none. |

## Success examples

A single schedule (`data` is an object):

```json
{ "success": true, "message": "Schedule retrieved", "data": { "id": "665f…", "name": "morning-report" } }
```

A list (`data` is an array):

```json
{ "success": true, "message": "Schedules retrieved", "data": [ { "id": "665f…" }, { "id": "6660…" } ] }
```

No payload (e.g. delete):

```json
{ "success": true, "message": "Schedule deleted", "data": null }
```

## Error shape

Errors keep the same envelope with `success: false` and (usually) `data: null`:

```json
{ "success": false, "message": "Schedule '665f…' not found", "data": null }
```

**Validation errors (HTTP 422)** put per-field issues in `data`:

```json
{
  "success": false,
  "message": "Validation failed",
  "data": [ { "field": "body.name", "error": "Field required" } ]
}
```

See [Errors](../errors.md) for the full status-code reference.

!!! tip
    Always branch on `success`, then read `data`. You never have to guess the
    response shape per endpoint — it is always this envelope.
