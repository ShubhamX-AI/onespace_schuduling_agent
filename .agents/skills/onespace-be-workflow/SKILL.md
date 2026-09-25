---
name: onespace-be-workflow
description: >
  The mandatory scope → track → plan → approve → execute → report workflow for
  every non-trivial backend task (feature, refactor, code audit, security audit,
  test campaign, debugging). Use it BEFORE touching code whenever the user asks
  to refactor, clean up, audit, review, "check for bad code", find
  vulnerabilities, add a feature, fix a bug, or raise test coverage — even when they phrase it casually ("fix this
  mess", "make it secure", "is this code ok"). Creates and maintains the
  `agent-tracking/` folder (scope, research, plan, progress, report) so every
  piece of agent work is structured and traceable.
---

# Workflow

Agents that jump straight into code produce changes nobody asked for, audits of
the wrong scope, and no record of why anything happened. This skill prevents
that. Every non-trivial task runs through seven phases, and each phase leaves a
file on disk before the next begins. The files are the audit trail: a reviewer
who never saw the conversation must be able to reconstruct what was asked, what
was decided, and what was done.

Trivial tasks (a question, a typo, a one-line rename) skip this skill. Unsure =
not trivial. Touching more than one file, any trust boundary (auth, input
parsing, external calls, secrets), or any public interface is never trivial.

Paths like `onespace-be-<skill>/references/<file>.md` name a sibling skill: resolve
them from the parent of this skill's base directory. Sibling missing? Tell the
user to install the whole pack.

---

## Phase 1 — Classify

Name the task type. It sets the slug and which skills apply.

| Type | Follow-on skill(s) |
|------|--------------------|
| `feature` | `onespace-be-build-feature` |
| `refactor` | `onespace-be-refactor-code` |
| `audit` | `onespace-be-audit-code` |
| `security` | `onespace-be-audit-security` |
| `test` | `onespace-be-write-tests` |
| `debug` | `onespace-be-debug` |
| `structure` | `onespace-be-structure-service` |
| `health` | `onespace-be-add-health-endpoint` |

A request can span types ("audit and fix"). Split it: the audit is one task, the
fix is a second task planned from the audit's findings. This keeps each report
honest about what was examined versus what was changed.

## Phase 2 — Bootstrap tracking (before asking anything)

The very first thing you write is the record of what the user asked — before the
scope interview, so the questions and answers are captured too. Create the
tracking layout if it is missing. It belongs in version control alongside the
code, but **you never commit, branch, or push on your own** — the user commits
it with their change, unless they ask you to. Creating these files
is not "starting work": no source file is touched.

```
agent-tracking/
├── INDEX.md                         # one row per task
├── plans/
│   └── <slug>/
│       ├── scope.md                 # the user's words + agreed scope
│       ├── plan.md                  # the approved plan (checklist)
│       └── progress.md              # step log, decisions, deviations
├── research/
│   └── <slug>.md                    # what was read / measured, and what it showed
└── reports/
    └── <slug>.html | <slug>.md      # the deliverable
```

**Slug**: `YYYY-MM-DD-<type>-<short-topic>`, lowercase, hyphenated, e.g.
`2026-09-24-security-payments-api`. Same slug everywhere for one task.

Copy the templates from this skill's `templates/` directory and fill them in:

- `INDEX.md` — create from `templates/INDEX.md` if absent; append one row now
  (status `scoping`), and update the row at every phase change.
- `plans/<slug>/scope.md` — from `templates/scope.md`. Quote the user's original
  request verbatim now. Fill the "Agreed scope" table as answers arrive, and log
  every question you ask (and its answer, or "awaiting answer") in the
  clarification log. If the topic is unclear, use a provisional slug and rename
  the folder once scope is agreed.

## Phase 3 — Scope interview (no work yet)

Do not read deeply, run scanners, or edit source until scope is agreed. A
quick look at the repo tree to ask sensible questions is fine.

Ask about every item below that the user has not already answered. Group the
questions into one message; offer concrete options and a recommended default so
the user can answer fast.

1. **Target** — whole repo, specific directories, specific files, a diff/branch,
   or specific endpoints?
2. **Depth** — `quick` (automated tools + top risks), `standard` (tools + manual
   review of every in-scope file), or `deep` (standard + data-flow tracing across
   modules, every trust boundary)?
3. **Out of scope** — tests? generated code? vendored code? infra/Docker? frontend?
4. **Constraints** — public API must not change? no new dependencies? no DB
   migrations? time box?
5. **Success criteria** — what does "done" look like? (e.g. "no High+ findings",
   "complexity ≤10 everywhere", "endpoint returns X with tests")
6. **Output** — report format: **HTML (default)** or **Markdown**? Severity
   cut-off for the report (all findings, or Medium and above)?
7. **Type-specific** —
   - refactor: may files move / be renamed? is behaviour allowed to change? (default no)
   - security: which ASVS level (L1 / **L2 default** / L3)? does the service call an LLM?
   - feature: acceptance criteria, API shape, auth rules, who can see what.
   - audit: fix nothing (default) or propose patches in the report?
   - debug: the bug report is most of the scope — ask only for missing
     symptom, expected behaviour, where/when, and hotfix vs proper fix
     (`onespace-be-debug`).

If an answer is vague ("just check everything", "make it good"), say what you
would assume and ask the user to confirm. Never silently assume scope — the most
expensive agent failure is doing a large amount of excellent work on the wrong
thing.

Record the questions in `scope.md` before you send them, then end your turn and
wait. When answers arrive, write them into `scope.md` (INDEX status stays
`scoping` until every row of "Agreed scope" is filled or explicitly defaulted).
If the user answers "use your defaults", record each default as the answer.

## Phase 4 — Research

Now read. Write findings to `research/<slug>.md` (template
`templates/research.md`) as you go, not at the end:

- **project structure** — read the `## Project structure` section of the repo's
  `AGENTS.md`. Missing, and the task will place or move code (feature,
  refactor)? Run `onespace-be-structure-service` now and settle the structure with the user
  before writing the plan. Record the structure in research.
- entry points and the files in scope (with line counts)
- how the pieces connect (a short dependency map)
- baseline measurements — run what the repo already has: tests, coverage,
  linters, type checker, and for security the scanners in `onespace-be-audit-security`.
  Record exact commands and summarised output. These numbers are the "before" in
  the final report.
- external facts you looked up (library versions, standards) with sources
- open questions for the user

If a tool the plan needs is not installed, record that and ask before installing
anything.

## Phase 5 — Plan, then stop

Write `plans/<slug>/plan.md` from `templates/plan.md`:

- goal (one sentence) and success criteria (from scope)
- skills that apply
- steps as a checkbox list; each step small enough to verify on its own
- files expected to change or be created
- design notes for features: the system design pass
  (`onespace-be-build-feature/references/system-design.md`)
- risks and how each is mitigated; delivery and rollback per
  `references/SAFE-DELIVERY.md` (small reversible steps, expand → contract,
  concrete rollback recipe)
- verification: exact commands and expected results

Show the plan to the user (summary in chat, path to the file) and **wait for
explicit approval**. "Looks good", "go ahead", "approved" count; silence and
follow-up questions do not. If the user changes the plan, edit `plan.md`, note
the change in `progress.md`, and ask again. Set INDEX status `approved`.

For `audit` and `security` tasks the "plan" is the review plan (which files,
which checklists, which tools); the output is a report, not code changes.

## Phase 6 — Execute

Before the first edit, load `onespace-be-coding-standards`; before creating any
file, load `onespace-be-busl-licence-compliance`.

Work through the checklist in order. After each step:

1. tick the box in `plan.md`
2. append to `progress.md` — what changed, why, commands run, result
3. run the step's verification; a red step is fixed before the next starts

When you discover something outside the approved scope (a bug next door, a
security hole in another module), **record it in `progress.md` under
"Out-of-scope observations" and tell the user**. Do not fix it unasked. Scope
creep is how a reviewed plan turns into an unreviewed diff.

Delegate where it helps: parallel read-only investigation, black-box test
writing, and a fresh-context review of the diff before the report
(`references/SUBAGENTS.md`). You stay responsible for everything they return.

Set INDEX status `in-progress`.

## Phase 7 — Report

Produce `agent-tracking/reports/<slug>.html` or
`agent-tracking/reports/<slug>.md` in the format the user chose. Always write
it there, never to the OS temp directory, the repo root, a hosted page (claude.ai
Artifact, gist, docs connector), or only to chat, so
the report sits next to its scope, plan, and progress. Build it from
`templates/report.html` or `templates/report.md`. Every report has:

1. **Summary** — what was asked, what was done, headline result
2. **Scope** — in / out, depth, constraints (link `scope.md`)
3. **Method** — tools run, checklists applied, standards referenced
4. **Current → Target** — diagrams of what exists and what changed
   (refactor, feature, structure, test; not audit/security, which change nothing)
5. **Findings** or **Changes** — per type:
   - audit/security: findings table (ID, severity, category, standard ref,
     `file:line`, evidence, impact, recommendation, status)
   - refactor: before/after metrics, each change with the named refactoring
   - feature: what was built, interface, tests added
6. **Verification** — commands run and results (before vs after)
7. **Out-of-scope observations** and **recommended next tasks**
8. **Trace** — links to scope, research, plan, progress

Reports are visual first. Follow `references/VISUAL-REPORT.md` for the
diagram patterns, the colour legend, and the visuals each report type must
include. The reviewer should grasp the change from the diagrams alone.

Script policy for HTML reports:

- **Refactor, feature, structure, test:** inline CSS plus the one Mermaid
  import already in the template. Nothing else external. These reports must
  hold no secrets, credentials, or security findings.
- **Audit and security:** a single self-contained file. Delete the Mermaid
  block; inline CSS, plain boxes and tables only, no external scripts, fonts, or CDNs.
  Audit findings are sensitive and reports get opened offline and attached to
  tickets.

Finish by setting INDEX status `done` with the report link, and give the user a
short chat summary plus the report path.

---

## Resuming work

When the user returns to a task, read `INDEX.md`, then the task's `scope.md`,
`plan.md`, and `progress.md` before doing anything. Continue from the first
unticked step. If the code has moved on since the plan was written, say so and
re-confirm the plan.

## Status values

`scoping` → `researching` → `awaiting-approval` → `approved` → `in-progress` →
`done` (or `blocked`, `cancelled` with a one-line reason).
