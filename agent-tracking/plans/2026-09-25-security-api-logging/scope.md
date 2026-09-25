# Scope — 2026-09-25-security-api-logging

- **Type:** security
- **Requested by:** repository owner (developer)
- **Date:** 2026-09-25

## Original request (verbatim)

> /onespace-be-audit-security -> take a look into the seccirity on the api side ..and logs

## Agreed scope

| Question | Answer |
|----------|--------|
| Target (paths / endpoints / diff) | API + logs + their sinks: `server.py`, `server_run.py`, `src/api/**`, `src/core/exceptions.py`, `src/core/config.py`, `src/core/logging/`, every log call site in `src/`, and the webhook/notify SSRF path reached from API input (`src/scheduling/actions.py`, `WebhookAction` in `src/core/db/db_schema.py`) |
| Depth (quick / standard / deep) | standard |
| Out of scope | tests/, docs/, site/, deploy scripts, MongoDB server hardening, scheduling internals not reached from API input |
| Constraints | report only; no source edits |
| Success criteria | every in-scope file reviewed; each finding traced to a standard ID and `file:line`; proposed patch per finding |
| Report format (HTML / MD) | HTML |
| Severity cut-off | all |
| Type-specific answers | ASVS L2; service calls no LLM (LLM checklist skipped); remediation = report + proposed patches |

## Assumptions confirmed with the user

- Deployment shape as in repo: `docker-compose.yml` publishes the API port; an upstream gateway setting `X-Owner-Id` is assumed but not enforced by code.

## Clarification log

| Question asked | User's answer |
|----------------|---------------|
| Which target? | API + logs + their sinks (recommended) |
| Review depth? | standard |
| ASVS level and output? | L2, HTML, all severities |
| Remediation in scope? | Report + proposed patches |
