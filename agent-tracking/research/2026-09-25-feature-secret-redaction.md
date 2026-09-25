# Research — 2026-09-25-feature-secret-redaction

## Project structure
No `## Project structure` section in `AGENTS.md`; the layout recorded in `CLAUDE.md` (Architecture) is followed: DTOs in `src/api/models/`, business rules in `src/scheduling/`, DB shape in `src/core/db/db_schema.py`.

## Files in scope
- `src/api/models/schedule.py` — `ScheduleRead.action: WebhookAction | None` serialises headers verbatim (S-004).
- `src/api/routes/v1/schedules.py:35,79` — create passes `model_dump()`, update passes `model_dump(exclude_unset=True)`; `changes["action"]` reaches the service as a dict.
- `src/scheduling/schedule_service.py:22,66` — `create_schedule`, `update_schedule`: the place for the masked-value merge rule (business rule, not HTTP).
- `src/scheduling/lifecycle.py:74` — `apply` `$set`s the `action` dict as given; no change needed.
- `src/scheduling/actions.py:56,61,64,86,112` — payload log, `logger.exception` on expected failure, error text embeds full URL + httpx message, notify failure logs traceback with URL (S-005).
- `src/scheduling/jobs.py:39-47` — copies `result.error` to `ScheduleRun.error` and `last_error`; fixed at the source, no change.

## Reuse
- `ValidationError` (`src/core/exceptions.py:52`) already maps to 422 in the envelope.
- `httpx.URL` (installed) parses scheme/host/path — no new parser.
- Pydantic 2 `field_serializer` — already the installed major; used for masking on output only.
- Test helpers: `tests/factories.py` (`build_schedule`, `build_webhook_action`), `tests/scheduling/test_actions.py` (`_mock_client`, `_allow_private`), `tests/conftest.py` client with `X-Owner-Id`.

## Baseline (2026-09-25, before any change)
- `uv run pytest -q`: 143 passed, coverage 94.55%.
- `uv run ruff check .`: All checks passed.

## External facts
- Pydantic `field_serializer` affects `model_dump`/JSON output only, not validation: https://docs.pydantic.dev/latest/concepts/serialization/#field_serializer
- `httpx.HTTPStatusError.__str__` includes the request URL (verified in installed httpx), so `str(exc)` must not reach records.
