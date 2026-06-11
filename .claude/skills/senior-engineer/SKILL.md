---
name: senior-engineer
description: Senior software engineer coding workflow. Use when implementing any non-trivial code change, feature, or fix. Understands the problem first, plans the work as a todo list, executes step by step, then runs a code-simplicity pass so the result is simple enough for a junior engineer to read and maintain. Triggers - "use senior engineer", "build this properly", "implement step by step", "/senior-engineer".
---

# Senior Engineer Coding Workflow

Work like a senior engineer: think before typing, keep changes small and
verifiable, and leave code that the next person — including a junior — can read
without a guide. Favour the simplest design that fully solves the problem.

Follow these four phases **in order**. Do not skip ahead.

## Phase 1 — Understand the problem

Before writing any code:

1. Restate the request in one or two sentences. If anything is ambiguous, ask
   the user instead of guessing.
2. Read the relevant existing code (use search/explore tools). Find patterns,
   helpers, and conventions already in the repo — reuse beats reinvention.
3. Identify constraints: tests, lint, the response/contract shape, public APIs
   that must not break.
4. State your understanding and intended approach briefly before starting.

## Phase 2 — Plan with a todo list

1. Break the work into small, ordered, independently-verifiable steps using the
   task tools (TaskCreate / TaskUpdate).
2. Each step should be one coherent change (one concern), not "do everything".
3. Mark exactly one task `in_progress` at a time; mark it `completed` only when
   it actually works.

## Phase 3 — Execute step by step

For each task:

1. Make the smallest change that completes that step.
2. Match the surrounding code: naming, structure, comment density, idioms.
3. Keep layers honest — don't leak DB models into the API, don't put business
   logic in endpoints, don't make inner layers import outer ones.
4. Run the relevant check (lint / tests / build) before moving on. If it fails,
   fix it before continuing — never mark a failing step done.

## Phase 4 — Simplicity pass (mandatory)

After the feature works, review what you wrote and ask: **could a junior
engineer read this and understand it in one pass?** If not, simplify.

Apply this checklist:

- **Less is more** — remove dead code, unused params, needless abstraction, and
  layers that only forward a call. One clear function beats three tiny indirections.
- **Name for intent** — a reader should understand a name without reading its body.
- **Avoid cleverness** — prefer the obvious construct over the compact-but-cryptic
  one. If a one-liner needs a comment to be understood, write the longer version.
- **Small functions, flat logic** — early returns over deep nesting; a function
  should do one thing.
- **Comments explain *why*, not *what*** — the code already says what.
- **Consistency** — follow the patterns already in the file/repo.

Then either fix it yourself, or delegate to the `code-simplifier` agent over the
changed files and apply its safe suggestions. Re-run lint/tests after.

## Definition of done

- The original problem is fully solved (not partially).
- Lint, tests, and build pass — and you ran them, not assumed them.
- The diff is the simplest version you could write that still does the job.
- A junior engineer could read the change and explain it back to you.
