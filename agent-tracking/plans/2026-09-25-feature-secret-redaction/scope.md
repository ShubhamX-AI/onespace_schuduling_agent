# Scope — 2026-09-25-feature-secret-redaction

- **Type:** feature (remediation of audit findings S-004, S-005)
- **Requested by:** repository owner (developer)
- **Date:** 2026-09-25

## Original request (verbatim)

> /onespace-be-build-feature -> implement the S-005 and S-004 from the "agent-tracking/plans/2026-09-25-security-api-logging"

Source findings: `agent-tracking/reports/2026-09-25-security-api-logging.html`
- **S-004** (Medium) — webhook `action.headers` stored in clear and returned on every read (`src/api/models/schedule.py:124`).
- **S-005** (Medium) — payload logged at INFO, full URL + httpx message in error text, which flows to logs, `last_error`, `ScheduleRun.error` and the notify body (`src/scheduling/actions.py:56,61,64,86,112`).

## Agreed scope

| Question | Answer |
|----------|--------|
| Target (paths / endpoints / diff) | S-004: `ScheduleRead` serialisation (`src/api/models/schedule.py`) and the update path that merges masked header values (`src/scheduling/schedule_service.py` / `lifecycle.py`). S-005: `src/scheduling/actions.py` log calls and error text; flows into `jobs.py` (`last_error`, `ScheduleRun.error`) and notify body |
| Depth (quick / standard / deep) | standard (feature) |
| Out of scope | encryption at rest (follow-up); `action.url` query tokens in reads; other audit findings S-001..S-003, S-006..S-011; rewriting existing stored `last_error`/run rows |
| Constraints | no new dependency; no DB migration; response field names/types unchanged (only header values masked); defaulted, not objected to |
| Success criteria | no header value in any schedule response; masked round-trip PATCH keeps stored secrets; no payload, query string, userinfo or httpx message in logs/`last_error`/run history/notify; tests per criterion; ruff + pytest green, coverage >= 80% |
| Report format (HTML / MD) | HTML |
| Severity cut-off | N/A (feature) |
| Type-specific answers | mask all header values as `***`; PATCH `***` keeps stored value for an existing header name, `***` for an unknown header = 422; no encryption now; S-005 fix as proposed in audit report |

## Assumptions confirmed with the user

- Other scope rows defaulted (stated in chat); user may override at plan approval.

## Clarification log

| Question asked | User's answer |
|----------------|---------------|
| S-004 masking rule: what do reads return for header values? | Mask all values (`***`) |
| S-004 PATCH semantics: client sends masked `***` values back in `action` — what happens? | Keep stored value; unknown header with `***` = 422 |
| S-004 encrypt header values at rest? | No, record as follow-up |
| S-005 error text / log level shape | Defaulted to audit patch: scheme+host+path, exception type, HTTP status; warning without traceback for delivery failures |
| Report format | HTML |

## Acceptance criteria

1. Every schedule response (create, get, list, update, pause, resume, run) returns `action.headers` with the same names and every value replaced by `***`. The stored document is unchanged.
2. PATCH with `action.headers` holding `***` for a header name the stored action already has (name compared case-insensitively) keeps the stored value; the webhook still sends the real secret.
3. PATCH or create with `***` for a header name that has no stored value returns 422 in the envelope and changes nothing.
4. PATCH with a real (non-`***`) header value replaces it, as today.
5. A fire with no action logs no payload.
6. A failed webhook delivery produces error text of the form `<METHOD> <scheme>://<host><path> failed: <ExceptionType>[ (HTTP <status>)]` — no query string, userinfo or httpx message. This text is what reaches `last_error`, `ScheduleRun.error` and the notify body.
7. Expected delivery failures log at WARNING without traceback; unexpected errors keep `logger.exception` but record only `Unexpected error: <ExceptionType>` as the run error.
8. A failed notify logs at WARNING with the exception type only, no URL and no traceback.
