---
name: python-service-structure
description: >
  The canonical folder layout, naming conventions, and README standard for
  OneSpace Python services (FastAPI + async). Use when scaffolding a new Python
  service, restructuring or cleaning up an existing one, deciding where a new
  module belongs, reviewing a layout, or when asked to "structure this repo",
  "where should this file go", "fix the folder structure", or "update the
  README". Self-contained — works unchanged in any repo it is copied into.
---

# Python Service Structure

Target state for every OneSpace Python service. A new developer should
understand where things live from the directory names alone, without reading a
single function body.

> **A great developer seeks simplicity. An idiot developer seeks complexity.**

If the task is a general refactor (splitting overgrown functions, renaming,
deleting dead code), follow the phased discipline in the `codebase-structuring`
skill — understand → audit → plan → **get approval** → execute → document. This
skill defines the *target layout* that discipline aims at; it does not replace it.

---

## Canonical layout

```
repo/
├── server.py                   # app entry only: router mounts, middleware,
│                               #   lifespan (resource init/close), exception handlers
├── server_run.py               # production runner (gunicorn/uvicorn workers)
├── pyproject.toml              # single manifest; license = "BUSL-1.1"
├── uv.lock
├── LICENSE                     # BUSL-1.1 (read-only)
├── NOTICE
├── THIRD_PARTY_LICENSES.md
├── README.md                   # see "README standard" below
├── AGENTS.md                   # mandatory skills for agents working in this repo
├── Dockerfile
├── docker-compose.yml
├── .env.example                # every var, safe placeholder values, no secrets
├── .agents/skills/             # repo-scoped agent skills
├── docs/                       # long-form docs (MkDocs), served if built
├── tests/                      # pytest suite, mirrors src/ layout
└── src/
    ├── api/                    # HTTP surface — no business logic
    │   ├── routes/             # one module per endpoint group
    │   │   ├── <area>.py
    │   │   └── v1/             # versioned subpackage; _common.py for shared deps
    │   └── models/             # pydantic request/response models, one file per scope
    │       └── response_schemas.py   # the shared response envelope
    ├── <domain>/               # business logic (e.g. agents/, billing/, ingest/)
    ├── services/               # external I/O clients ONLY — one dir per upstream
    │   └── <upstream>/<upstream>_service.py
    └── core/                   # cross-cutting infrastructure
        ├── config.py           # ONE Settings singleton reading .env
        ├── exceptions.py       # AppError hierarchy + handlers that emit the envelope
        ├── db/
        │   ├── db_connect.py   # connection lifecycle (init/close)
        │   ├── db_schema.py    # document/table models
        │   └── functions/      # query helpers, one file per concern
        ├── middleware/
        └── logging/logger.py   # setup_logging() once, get_logger(__name__) everywhere
```

Grow it by adding siblings at the right layer, never by nesting a new concern
inside an unrelated one.

## Layer rules

Each rule below exists because breaking it is what actually rots a service.

**`server.py` is wiring, not logic.** Routers, middleware, lifespan, exception
handlers. If it contains a business rule, that rule belongs in `src/<domain>/`.

**`src/api/` is the HTTP surface only.** A route function validates input,
delegates, and shapes the response. No queries, no external calls, no branching
business rules inside a route body. Shared dependencies (auth, tenant header)
live in a `_common.py` in the route package, not duplicated per route.

**`src/api/models/` holds pydantic models, one file per scope** (`common.py`,
`<feature>.py`, `response_schemas.py`). Never mix models into route modules.

**`src/services/` is external I/O and nothing else.** One directory per upstream
system. Each service module exposes the pair:

- `call_<x>_endpoint(...)` — performs the request
- `condense_<x>_response(...)` — strips envelope noise at the boundary, so callers
  never see the upstream's wire format

**Condense at the boundary.** Upstream payloads are normalised the moment they
arrive. Envelope noise must not leak upward into domain code.

**`src/core/config.py` owns configuration.** One `Settings` class, one module-level
singleton, every value read there. Scattered `os.getenv` calls elsewhere are a
defect — they hide the config surface and break `.env.example`.

**One response envelope.** Success *and* every error path return the same shape.
Register exception handlers centrally in `server.py` so no route hand-rolls an
error body.

**`tests/` mirrors `src/`.** `src/services/rag/rag_service.py` →
`tests/services/rag/test_rag_service.py`. Non-trivial logic leaves at least one runnable check.

**One responsibility per file.** If a file needs a table of contents, split it.
Typical split: `builder.py` (construction) + `prompts.py`/`models.py` (data) +
`<x>_service.py` (I/O).

**One job per function.** If describing it needs the word "and", split it.

**Names tell the story.** `snake_case` modules, no `utils.py` dumping ground, no
`tmp`, `data2`, `handleStuff`. A public name should reveal intent without the body.

**No dead code.** Delete it. Never leave commented-out blocks behind.

**Docstrings on public functions/classes** stating *what* and *why*. The code
already shows *how*.

## Where does this new file go?

| It … | Put it in |
|------|-----------|
| defines an HTTP endpoint | `src/api/routes/` (versioned subdir if the API is versioned) |
| is a request/response shape | `src/api/models/` |
| talks to a third-party or sibling service over the network | `src/services/<upstream>/` |
| encodes a business rule or orchestration | `src/<domain>/` |
| reads env / configures the process | `src/core/config.py` (extend, don't add a new config module) |
| defines error types / registers exception handlers | `src/core/exceptions.py` (registered centrally in `server.py`) |
| touches the database | `src/core/db/` (`db_schema.py` for models, `functions/` for queries) |
| wraps every request | `src/core/middleware/` |
| is a test | `tests/`, named after the module under test |

## README standard

The README is part of the deliverable, not an afterthought. **A structure change
is not complete until the README reflects it in the same change.**

Required sections, in order:

1. **Title + what it is** — one paragraph, plus the core model/concepts if the
   service has a non-obvious one
2. **Response envelope** — the shape every endpoint returns
3. **Requirements** — Python version, external services (DB, queues, upstreams)
4. **Installation** — local (`uv sync`, dev server command) *and* Docker
5. **Environment** — table of every var: name, default, note. Must match
   `src/core/config.py` and `.env.example` exactly
6. **Endpoints** — quick-reference table: method, path, purpose
7. **Project Structure** — the directory tree with a one-line comment per entry
8. **Data stores** — collections/tables, what keys them, what they hold
9. **Stack** — layer → technology table
10. **Licence** — from the `busl-licence-compliance` skill

Rules: if it exists, read it before changing anything. If it is missing, create
it. After any change, re-check the **whole** README for staleness — env vars,
endpoints, and the structure tree drift first and fastest.

## Working procedure

1. **Read before changing.** Walk the tree, read the entrypoint, map module
   dependencies. Never restructure code you have not read.
2. **Audit** against the layer rules above; list each violation with its path.
3. **Plan** — before/after tree, file splits, function decompositions, renames
   with rationale, docs to update. **Present the plan and wait for approval.**
4. **Execute** — `git mv` to preserve history, move code, split oversized files
   and functions, update every import, delete dead code. External behaviour must
   not change: no feature changes, no regressions.
5. **Document** — update the README (tree, env, endpoints), add docstrings to new
   public APIs.
6. **Licence** — run the `busl-licence-compliance` skill over every file created
   or moved, so nothing lands without a header:
   ```bash
   python .agents/skills/busl-licence-compliance/scripts/add_license_headers.py --root .
   ```
7. **Verify** — the app still boots, the test suite result is no worse than the
   baseline captured in step 1, config/build files still parse.

## New service scaffold

Minimum viable repo — do not scaffold layers nothing uses yet. Add
`src/<domain>/`, `src/core/db/`, and `src/core/middleware/` when the first real
need arrives, not "for later" (`src/services/` likewise appears only once the
first upstream client exists).

```
server.py  pyproject.toml  README.md  .env.example  Dockerfile
LICENSE  NOTICE  THIRD_PARTY_LICENSES.md  AGENTS.md
src/api/routes/  src/api/models/response_schemas.py
src/core/config.py  src/core/logging/logger.py
tests/
```

Then run the `busl-licence-compliance` new-repository checklist before the first
commit.

---

## Porting this skill to another repository

1. Copy the whole `python-service-structure/` directory into the target repo's
   `.agents/skills/`.
2. Mirror it to other agent toolchains in use (symlink keeps one source of truth):
   ```bash
   mkdir -p .claude/skills .opencode/skills
   ln -s ../../.agents/skills/python-service-structure .claude/skills/python-service-structure
   ln -s ../../.agents/skills/python-service-structure .opencode/skills/python-service-structure
   ```
   On Windows PowerShell use `New-Item -ItemType SymbolicLink -Target ../../.agents/skills/python-service-structure`
   per target (or a directory junction `-ItemType Junction` if symlinks need
   elevation); copy the directory instead if the toolchain does not follow links.
3. Ensure the repo has a root `AGENTS.md` naming this skill as mandatory.
4. Copy `busl-licence-compliance/` alongside it — step 6 of the working procedure
   depends on it.
