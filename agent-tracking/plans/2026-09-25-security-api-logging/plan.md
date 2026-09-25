# Security audit — API layer + logging (review plan)

Slug: `2026-09-25-security-api-logging`

## Context
User request (verbatim): "take a look into the seccirity on the api side ..and logs"
Type `security` — onespace-be-workflow phases 1–3 done in chat; onespace-be-audit-security phases 4–7 remain.
Plan mode blocked writing `agent-tracking/`; step 1 creates it and records scope + this plan there.

## Agreed scope
| Item | Answer |
|------|--------|
| Target | API + logs + their sinks: `server.py`, `src/api/**`, `src/core/{exceptions,config}.py`, `src/core/logging/`, every log call site, plus SSRF path reached from API input (`src/scheduling/actions.py`, webhook fields in `db_schema.py`) |
| Depth | standard (scanners + manual review of every in-scope file) |
| Out of scope | tests/, docs/, site/, deploy scripts, Mongo server hardening, scheduling internals not reached from API input |
| ASVS level | L2 |
| LLM calls | none (no LLM client in deps) — LLM checklist skipped |
| Output | HTML, all severities, `agent-tracking/reports/2026-09-25-security-api-logging.html`, self-contained, no scripts |
| Remediation | report + proposed patches (diffs in report); no source edits |

## Steps
1. [x] Bootstrap `agent-tracking/` from `.claude/skills/onespace-be-workflow/templates/` (INDEX row, scope.md with clarification log, plan.md = this, progress.md).
2. [x] Phase 4 scanners (ephemeral, no project dep changes), output summarised in `research/<slug>.md`:
   - `uvx ruff check --select S src server.py server_run.py` (bandit rules)
   - `uvx semgrep scan --config p/python --config p/fastapi src server.py`
   - `uvx pip-audit` against `uv export --no-dev` requirements
   - `gitleaks detect` if installed, else record "not run"
   Triage each hit: confirmed / false positive (reason) / manual check.
3. [x] Phase 6 manual review, trust boundaries first, checklist per skill (access control, input limits, SSRF, config, logging, secrets, supply chain). Confirm each candidate below at `file:line`, check Starlette `ServerErrorMiddleware` debug behaviour and Python 3.12 `ipaddress` handling of IPv4-mapped IPv6 before rating.
4. [x] Phase 7 report with severity tiles/bar, source→sink boxes for High+, proposed patch per finding, Method + coverage statement. INDEX status `done`.

## Candidate findings to confirm (from first read)
| # | Area | Location | Candidate |
|---|------|----------|-----------|
| 1 | Access control | `src/api/routes/v1/_common.py:13` | `X-Owner-Id` trusted as-is; compose publishes port on all interfaces — any client reaching service reads/edits any tenant (BOLA) when gateway bypassed |
| 2 | SSRF | `src/scheduling/actions.py:124-141` | check-then-connect: resolve once, httpx resolves again (DNS rebinding TOCTOU); no multicast/unspecified check; IPv4-mapped IPv6 handling to verify |
| 3 | Resource limits | `schedules.py` create, `db_schema.py:WebhookAction` | no per-owner quota, no rate limit, no body size cap, unbounded `payload`; interval of 1s × 11 attempts × 300s timeout = outbound amplification / relay |
| 4 | Pagination | `schedule_service.py:list_schedules` | unbounded list |
| 5 | Secrets exposure | `db_schema.py:WebhookAction.headers`, `ScheduleRead.action` | webhook auth headers stored plaintext, returned in every read |
| 6 | Logging / CWE-532 | `actions.py:56` | full `payload` logged at INFO |
| 7 | Logging / CWE-532 | `actions.py:61-64,83` | error string embeds full URL (query tokens) — goes to logs, `last_error`, run history, notify body |
| 8 | Logging / A09 | `logger.py`, `exceptions.py` | no request id, no access log of 401/404/422 security events, plain-text format; `/validate` + `/health` unauthenticated with no logging |
| 9 | Info leak | `health.py:48` | unauthenticated `/health` returns raw exception text (pymongo topology text holds host:port) |
| 10 | Config | `server.py:47` | `debug=True` from env makes Starlette return tracebacks, bypassing envelope handler; `/docs`, `/redoc`, `/openapi.json` always on |
| 11 | Config | `server.py` | no security headers / CORS policy (API-only: Info) |
| 12 | Input | `_common.py` | `owner_id` no length/charset bound |
| 13 | Supply chain | `uv.lock` | pip-audit result |

## Verification
- Every reported finding re-opened at cited `file:line`; each cites OWASP/API/CWE/ASVS id.
- `git status` shows only `agent-tracking/` added; no `src/` change.
- Report opens offline, no external script/font.
