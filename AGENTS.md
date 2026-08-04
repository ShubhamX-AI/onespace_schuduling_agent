# AGENTS.md

Guidance for AI coding agents working in this repository.

## Mandatory skills

Load and follow these skills when their trigger applies — `.agents/skills/` on
its own is passive; an agent has to be told to apply them:

- `busl-licence-compliance` — every new/moved source file needs the BUSL-1.1
  header; before any commit touching source files, verify headers and the root
  licence files. This repo is **BUSL-1.1**, not open source.
- `python-service-structure` — the canonical layout: `src/api/` (HTTP surface),
  `src/scheduling/` (domain), `src/core/` (cross-cutting). New files go where
  the skill says; README changes ship in the same change.
- `python-testing` — pytest suite under `tests/` mirroring `src/`; every change
  under `src/` ships with its test; 80% coverage floor.
- `coding-skills` — senior-engineer mindset for all coding tasks.
- `senior-engineer` — understand → plan → execute → simplicity pass for any
  non-trivial change.

## Quality gates

Run all three before calling work done:

```bash
uv run ruff check .
uv run ruff format .
uv run pytest -q
```
