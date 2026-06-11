# OneSpace Scheduling Service

A programmable **alarm clock for your other services**:

> *"At this time, call this URL with this payload."*

You create a **schedule** over a REST API. The service stores it and, when its
**trigger** fires (an interval, a cron expression, or a one-shot date), it runs
the schedule's **action** — today, an outbound **webhook** (an HTTP call) to any
service you choose. Firing is timezone-aware and survives restarts.

The scheduler keeps time and delivers the call. The actual work belongs to
whatever service receives it.

```
            create                         on trigger
 Client  ──────────▶  Scheduling Service  ───────────▶  Your other service
          POST /schedules                  HTTP webhook   (does the real work)
```

## The three pieces of a schedule

| Piece | Question it answers | Where it's documented |
| ----- | ------------------- | --------------------- |
| **Trigger** | *When* does it fire? | [Triggers](concepts/triggers.md) |
| **Action**  | *What* happens on fire? | [Actions](concepts/actions.md) |
| **Payload** | *What data* is sent? | sent as the webhook body — [Actions](concepts/actions.md) |

## Quickstart

Create a schedule that calls a webhook every weekday at 09:00 New York time:

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H 'Content-Type: application/json' \
  -d '{
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
    }
  }'
```

Every response uses the same [envelope](concepts/response-envelope.md):

```json
{
  "success": true,
  "message": "Schedule created",
  "data": { "id": "665f...", "name": "morning-report", "next_run_at": "2026-06-12T13:00:00+00:00", "...": "..." }
}
```

## Where to go next

- New here? Read [Schedules](concepts/schedules.md) for the full anatomy and field reference.
- Want every timing option? [Triggers](concepts/triggers.md).
- Want to drive another service? [Actions](concepts/actions.md).
- Need a worked example for your case? [Recipes](recipes.md) covers every possibility.
- Full endpoint list with payloads and responses? [API Reference](api/schedules.md).

!!! tip "Two doc surfaces"
    This guide explains *concepts and recipes*. For the live, auto-generated
    OpenAPI schema and a try-it console, open **`/docs`** (Swagger UI) on the
    running service.
