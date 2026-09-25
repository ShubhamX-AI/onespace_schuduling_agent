# Plan — 2026-09-25-feature-secret-redaction

**Goal:** stop webhook secrets leaving through API reads (S-004) and stop payload/URL secrets reaching logs, run records and notify callbacks (S-005).

**Success criteria:** acceptance criteria 1–8 in `scope.md`, each with a test; ruff check + format clean; full suite green; coverage ≥ 80%.

**Skills:** onespace-be-build-feature, onespace-be-coding-standards, onespace-be-write-tests, onespace-be-busl-licence-compliance (no new files expected, so header check only).

## Design notes (system design pass)
- Numbers: ≤ 50 headers per action; merge is O(headers). No hot path change.
- Data / invariants: stored document keeps real header values; `***` never stored as a header value (rejected or resolved before write). No migration.
- Concurrency / idempotency: merge reads the stored action loaded by `get_schedule` in the same request; a concurrent PATCH race is last-write-wins, same as today.
- Outbound calls: unchanged behaviour; only error text and log level change.
- Limits: N/A — no new input.
- Compatibility: response shape unchanged; header values now `***`. Clients that echoed full actions back keep working (criterion 2). Clients that relied on reading secrets back lose that — intended. `last_error` text format changes (docs updated).
- Observability: delivery failures still logged (WARNING, schedule id + safe error text); unexpected errors keep traceback.

## Interface
- `src/core/db/db_schema.py`: `MASKED_VALUE = "***"` constant beside `WebhookAction`.
- `ScheduleRead`: `field_serializer("action")` returns action with every header value `MASKED_VALUE`.
- `schedule_service._unmask_headers(action: dict, stored: WebhookAction | None) -> dict`: replaces `***` with the stored value (case-insensitive name match) or raises `ValidationError` (422). Called by `create_schedule` (stored = None) and `update_schedule` when `"action"` is in changes.
- `actions._safe_target(url) -> str`: `scheme://host[:port]path`.
- HTTP surface: unchanged routes; PATCH/POST gain one new 422 case (criterion 3).

## Steps
1. [x] S-005: `actions.py` — drop payload from log; `_safe_target`; error text = method + safe target + exception type + HTTP status; `logger.warning` for `WebhookError`; unexpected error recorded as `Unexpected error: <Type>`; notify failure `logger.warning` with type only. Update/add tests in `tests/scheduling/test_actions.py` (criteria 5–8).
2. [x] S-004 output: `MASKED_VALUE` + `ScheduleRead` serializer; tests in `tests/api/models/test_schedule_models.py` and one route test (criterion 1).
3. [x] S-004 input: `_unmask_headers` in service, wired into create + update; tests in `tests/scheduling/test_schedule_service.py` and route test for 422 (criteria 2–4).
4. [x] Docs: `docs/api/schedules.md`, `docs/concepts/actions.md` (masked reads, `***` round-trip, new `last_error` format), README if it shows headers/errors.
5. [x] Self-review (reviewer subagent), gates, report `agent-tracking/reports/2026-09-25-feature-secret-redaction.html`.

## Files expected to change
`src/scheduling/actions.py`, `src/core/db/db_schema.py`, `src/api/models/schedule.py`, `src/scheduling/schedule_service.py`, tests for each, `docs/api/schedules.md`, `docs/concepts/actions.md`.

## Risks and rollback
- Risk: masked value accidentally stored, breaking a webhook — mitigated by criterion 2/3 tests. Risk: less diagnostic detail in `last_error` — type + HTTP status + safe target remain; traceback kept for unexpected errors.
- Each step is independent and revertable with `git revert` of its commit (user commits); no data migration, so rollback is code-only.

## Verification
`uv run ruff check .` → All checks passed; `uv run ruff format --check .` → clean; `uv run pytest -q` → all pass, coverage ≥ 80%.
