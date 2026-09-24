# Domain glossary

**Schedule** — a stored definition of *when* (trigger) and *what* (action) to fire, owned by one `owner_id`. Status is `active` (armed) or `paused` (kept, not firing).

**Trigger** — the WHEN: `date` (one-shot), `interval` or `cron`, evaluated in the schedule's IANA timezone, optionally inside a start/end window. Its five fields form a **trigger spec** (`src/scheduling/triggers.py:TriggerSpec`), shared by the request models. A trigger is **armable** when it is valid and still has a future fire; `/validate`, create and resume all use that same check (`armable_trigger`).

**Action** — the WHAT: today only `webhook`, which sends the schedule's `payload` as the HTTP body.

**Run** — one fire of a schedule. Recorded as a `ScheduleRun` document; its outcome also updates the schedule's run summary (`last_*`, `consecutive_errors`). The Run module (`src/scheduling/jobs.py:execute_schedule`) owns a fire end to end: load, action, run summary, notify, history.

**Schedule lifecycle** — every status transition of a schedule (create, pause, resume, edit, delete, auto-pause) together with arming or disarming its APScheduler job, plus queuing a run-now. Lives in `src/scheduling/lifecycle.py`, the only module that touches jobs. A failed step always leaves the schedule in the state that does not fire; a schedule with no future fire is never armed.

**Auto-pause** — the lifecycle pausing an active schedule after `consecutive_error_threshold` failed runs in a row. Resume resets the count.
