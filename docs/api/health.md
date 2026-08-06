# API Reference — Health

## Health check

`GET /health` → **always 200**

A deep probe: it pings every dependency a real request needs — MongoDB and the
APScheduler engine — concurrently, and reports each one. It is mounted outside
the `/api/v1` prefix and needs **no `X-Owner-Id` header and no auth**.

!!! warning "Read `data.status`, not the HTTP status code"
    This endpoint answers **200 even when every dependency is down**. A 5xx here
    would let one blipping dependency pull every instance of the service out of
    load-balancer rotation at once — turning a degraded dependency into a total
    outage, with the diagnostic endpoint unreachable behind the LB. Alert on
    `data.status == "degraded"`.

**Healthy:**

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "status": "ok",
    "version": "0.1.0",
    "uptime_s": 1421.7,
    "checks": {
      "mongodb": { "ok": true, "latency_ms": 3.1 },
      "scheduler": { "ok": true, "latency_ms": 0.0 }
    }
  }
}
```

**Degraded** (MongoDB unreachable):

```json
{
  "success": false,
  "message": "degraded",
  "data": {
    "status": "degraded",
    "version": "0.1.0",
    "uptime_s": 12.4,
    "checks": {
      "mongodb": { "ok": false, "latency_ms": 3001.2,
                   "error": "ServerSelectionTimeoutError: connection refused" },
      "scheduler": { "ok": true, "latency_ms": 0.0 }
    }
  }
}
```

| Field | Meaning |
| ----- | ------- |
| `status` | `ok` when every check passes, else `degraded`. `success` mirrors it. |
| `version` | Service version (`APP_VERSION`, also the OpenAPI version). |
| `uptime_s` | Seconds since process start — tells "still broken" from "crash-looping". |
| `checks.<name>` | Per-dependency `ok` + `latency_ms`; `error` (type + message, never a URI or credential) only on failure. |

The check names — `mongodb`, `scheduler` — are contract: dashboards key off
them, so renaming one breaks whoever monitors the service.

Each probe runs under its own short timeout, `HEALTH_PROBE_TIMEOUT_S`
(default `3` seconds), so a hung dependency cannot make `/health` the slowest
route in the service.

Container/orchestrator probes may poll this path, but configure them to treat
the response as always-healthy at the HTTP level. If traffic really must be
gated on dependency state, add a separate `/health/ready` that returns 503 —
do not overload this one.
