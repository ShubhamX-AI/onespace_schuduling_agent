# API Reference — Health

## Health check

`GET /api/v1/health` → **200**

Liveness/readiness probe. Pings MongoDB and reports the result. The envelope's
`success` reflects database reachability.

**Healthy:**

```json
{ "success": true, "message": "ok", "data": { "database": true } }
```

**Degraded** (database unreachable):

```json
{ "success": false, "message": "degraded", "data": { "database": false } }
```

Use this for container/orchestrator health probes.
