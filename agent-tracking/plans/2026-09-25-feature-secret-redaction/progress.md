# Progress — 2026-09-25-feature-secret-redaction

## Log

### 2026-09-25 — Scope, research, plan
- **Changed:** created scope.md, research/2026-09-25-feature-secret-redaction.md, plan.md; INDEX row.
- **Why:** workflow phases 1–5.
- **Commands / result:** baseline `uv run pytest -q` 143 passed, 94.55% coverage; `uv run ruff check .` clean.
- **Decision / deviation:** `***` on create is also rejected (422), to match the "unknown header with `***`" rule.

### 2026-09-25 — Plan approved
- User replied "approved".

### 2026-09-25 — Step 1: S-005 secret-free errors and logs
- **Changed:** `src/scheduling/actions.py` — payload dropped from the no-action log; `_failure_message` builds error text from method, scheme/host[:port]/path (via `httpx.URL.copy_with`), exception type and HTTP status; `WebhookError` logged at WARNING without traceback; unexpected errors keep `logger.exception` but record `Unexpected error: <Type>`; notify failure logs WARNING with type only.
- **Tests:** 5 new + 1 updated in `tests/scheduling/test_actions.py` (criteria 5–8). All 6 fail against the old `actions.py` (checked by stashing the source).
- **Decision / deviation:** port kept in the target text (not secret, helps diagnosis).

### 2026-09-25 — Step 2: S-004 masked reads
- **Changed:** `MASKED_VALUE = "***"` in `src/core/db/db_schema.py`; `ScheduleRead._mask_header_values` `field_serializer` returns a masked `WebhookAction` copy, so the OpenAPI schema is unchanged.
- **Tests:** 2 model tests, 1 route test (criterion 1).

### 2026-09-25 — Step 3: S-004 masked writes
- **Changed:** `schedule_service._unmask_headers`, called from `create_schedule` (no stored action) and `update_schedule` when `action` is sent.
- **Tests:** 4 service tests, 1 route 422 test (criteria 2–4).

### 2026-09-25 — Step 4: docs
- **Changed:** `docs/api/schedules.md` (masked example, write-only note, PATCH `***` rule, run error example), `docs/concepts/actions.md` (headers row, error text format), `README.md` (headers row).

### 2026-09-25 — Gates
- `uv run ruff check .`: All checks passed. `uv run pytest -q`: 156 passed, coverage 96.48% (was 143, 94.55%). BUSL `--check`: 0 files missing a header.
- `uv run ruff format --check .`: 2 files would be reformatted — `server_run.py` and `.agents/skills/.../add_license_headers.py`. Both untouched by this change and flagged identically before it; left as is.

### 2026-09-25 — Step 5: review and report
- Reviewer subagent (fresh context, plan + criteria + diff): no findings.
- Report: `agent-tracking/reports/2026-09-25-feature-secret-redaction.html` (no scripts; diagrams as boxes and tables because the report covers security fixes).

## Out-of-scope observations

| Observation | Location | Suggested follow-up |
|-------------|----------|---------------------|
| `action.url` query-string tokens are still returned in reads | `src/api/models/schedule.py` | separate task if URLs carry secrets |
| Header values remain in clear at rest | `src/core/db/db_schema.py` | encryption-at-rest task (key management + migration) |
| `ruff format --check` flags `server_run.py` and `.agents/skills/onespace-be-busl-licence-compliance/scripts/add_license_headers.py` | repo root | one-line formatting task |
