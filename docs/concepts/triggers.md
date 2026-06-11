# Triggers — *when* a schedule fires

A trigger is `trigger_type` + `trigger_args`. The args are passed straight to
[APScheduler](https://apscheduler.readthedocs.io/), so anything those triggers
accept works here.

Every schedule also carries a **`timezone`** (IANA, default `UTC`) so it fires
at the intended local time regardless of the server's clock.

## At a glance

| You want… | `trigger_type` | `trigger_args` |
| --------- | -------------- | -------------- |
| Fire once at a specific time | `date` | `{"run_date": "2026-06-12T10:00:00"}` |
| Fire roughly now / one-off | `date` | `{"run_date": "<now-ish ISO>"}` (or use [run now](../api/schedules.md#run-now)) |
| Tomorrow at 10:00 | `date` | `{"run_date": "2026-06-12T10:00:00"}` |
| Every N seconds/minutes/hours/days | `interval` | `{"hours": 1}` / `{"seconds": 30}` |
| Every day at a fixed time | `cron` | `{"hour": 9, "minute": 0}` |
| Weekdays only | `cron` | `{"hour": 9, "minute": 0, "day_of_week": "mon-fri"}` |

## `date` — one-shot

Fires exactly once, then the schedule stops firing.

```json
{ "trigger_type": "date", "trigger_args": { "run_date": "2026-06-12T10:00:00" } }
```

`date` does **not** accept a `start_date`/`end_date` window.

## `interval` — every N

Repeats forever (or within an optional window). Combine units freely.

```json
{ "trigger_type": "interval", "trigger_args": { "minutes": 15 } }
```

Accepted units: `weeks`, `days`, `hours`, `minutes`, `seconds`.

## `cron` — calendar-style

Fires on calendar fields. Omitted fields behave like cron defaults.

```json
{ "trigger_type": "cron",
  "trigger_args": { "hour": 9, "minute": 0, "day_of_week": "mon-fri" } }
```

Common fields: `year`, `month`, `day`, `week`, `day_of_week`, `hour`, `minute`,
`second`. `day_of_week` accepts `mon-fri`, `sat,sun`, `0-6`, etc.

## Timezone

```json
{ "timezone": "Asia/Kolkata" }
```

A `cron` of `{"hour": 9}` with `timezone: "Asia/Kolkata"` fires at 09:00 IST,
not 09:00 server time. Unknown timezones are rejected at create time.

## Active window (`interval` / `cron`)

Bound a repeating schedule to a date range:

```json
{
  "trigger_type": "cron",
  "trigger_args": { "hour": 9 },
  "start_date": "2026-07-01T00:00:00",
  "end_date": "2026-09-30T23:59:59"
}
```

The schedule only fires between `start_date` and `end_date`.

## Validate before saving

Check a trigger spec without creating anything — see
[`POST /validate`](../api/schedules.md#validate-a-trigger).

```bash
curl -X POST http://localhost:8000/api/v1/schedules/validate \
  -H 'Content-Type: application/json' \
  -d '{ "trigger_type": "cron", "trigger_args": { "hour": 9 }, "timezone": "Asia/Kolkata" }'
```
