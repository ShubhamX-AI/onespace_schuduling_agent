# Progress — 2026-09-25-security-api-logging

## Log

### 2026-09-25 — Step 1: bootstrap tracking
- **Changed:** created `agent-tracking/` (INDEX, scope, plan, progress, research).
- **Why:** workflow phase 2; plan mode blocked it earlier, scope was agreed in chat first.
- **Decision / deviation:** tracking created after scope answers instead of before (harness plan mode allowed only the plan file).

### 2026-09-25 — Step 2: automated pass
- **Commands / result:** ruff 0.16.9 `S,BLE,ASYNC` = 4 hits (all false positive); semgrep 1.178.0 `p/python p/owasp-top-ten p/secrets` = 1 hit (false positive); pip-audit 2.10.1 = 7 advisories in 3 packages (low reachability); gitleaks not installed = not run. Details in `research/2026-09-25-security-api-logging.md`.

### 2026-09-25 — Step 3: manual review
- Checklist areas done: access control, authentication, injection, input validation and resource limits, SSRF, files and paths, deserialization, secrets and crypto, configuration, supply chain, logging and error handling. LLM: not applicable.
- Runtime checks: Python 3.12.3 `ipaddress` flags IPv4-mapped IPv6 loopback/private correctly; `100.64.0.1` and `224.0.0.1` pass the guard. httpx `follow_redirects` default False. Starlette `ServerErrorMiddleware` returns traceback page when `debug=True`. `IntervalTrigger` with `seconds=0.01` passes `armable_trigger`.

### 2026-09-25 — Step 4: report
- Written `agent-tracking/reports/2026-09-25-security-api-logging.html` (no scripts). 2 High, 4 Medium, 3 Low, 2 Info.

## Out-of-scope observations

| Observation | Location | Suggested follow-up |
|-------------|----------|---------------------|
| `docker system prune -a -f` on every deploy removes all unused images host-wide | `deploy.sh` | review deploy script separately |
| MongoDB URI default has no credentials/TLS; compose has no Mongo service despite CLAUDE.md saying api + mongo | `.env.example`, `docker-compose.yml` | infra hardening task |
| Run-now job may overlap a scheduled fire (noted in code) | `src/scheduling/lifecycle.py:118` | code audit |
