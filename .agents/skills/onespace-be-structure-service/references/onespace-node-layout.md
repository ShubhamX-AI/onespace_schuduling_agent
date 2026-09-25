# Variant: OneSpace Node.js layout (layered by layer)

The layout existing OneSpace Node.js services use. It is **layered by technical
layer**, with one OneSpace-specific meaning to watch: here `services/` holds
**external I/O clients only** (one directory per upstream), and business logic
lives in `src/<domain>/`. In the generic layered layouts (`node-layouts.md`)
`services/` means use-case logic instead. When a repo uses this variant, record
that definition in its `## Project structure` section.

Choose this variant when the repo already follows it. For new services the
default proposal is layered-by-feature (see `node-layouts.md`).

## Canonical layout

```
repo/
├── src/
│   ├── server.ts               # entry only: build app, listen, graceful shutdown
│   ├── app.ts                  # app factory: middleware, route mounts, error handler
│   │                           #   (exported so tests can build the app without listening)
│   ├── api/                    # HTTP surface — no business logic
│   │   ├── routes/             # one module per endpoint group
│   │   │   ├── <area>.routes.ts
│   │   │   └── v1/             # versioned subfolder; common.ts for shared guards
│   │   └── schemas/            # zod request/response schemas, one file per scope
│   │       └── envelope.ts     # the shared response envelope
│   ├── <domain>/               # business logic (e.g. billing/, ingest/)
│   ├── services/               # external I/O clients ONLY — one dir per upstream
│   │   └── <upstream>/<upstream>.service.ts
│   └── core/                   # cross-cutting infrastructure
│       ├── config.ts           # ONE zod-validated config object from process.env
│       ├── errors.ts           # AppError hierarchy + central error handler
│       ├── logger.ts           # one pino instance; child loggers per module
│       ├── db/
│       │   ├── connection.ts   # connect / close
│       │   ├── models/         # schemas / models
│       │   └── queries/        # query helpers, one file per concern
│       └── middleware/
├── tests/                      # vitest suite, mirrors src/
├── package.json                # "license": "BUSL-1.1", "type": "module", engines.node
├── package-lock.json           # or pnpm-lock.yaml — committed
├── tsconfig.json               # strict
├── eslint.config.js            # flat config
├── .prettierrc
├── vitest.config.ts
├── LICENSE  NOTICE  THIRD_PARTY_LICENSES.md
├── README.md                   # see "README standard"
├── AGENTS.md
├── Dockerfile  docker-compose.yml
├── .env.example                # every var, safe placeholders, no secrets
└── .agents/skills/
```

Grow it by adding siblings at the right layer, never by nesting a new concern
inside an unrelated one.

## Layer rules

**`server.ts` is process wiring.** Build the app from `app.ts`, listen, handle
`SIGTERM`/`SIGINT` (stop accepting, drain, close DB and clients, exit), register
`unhandledRejection` / `uncaughtException` handlers that log and exit.

**`app.ts` composes, it does not decide.** Middleware order, route mounts, the
single error handler. No business rule lives here.

**`src/api/` is the HTTP surface only.** A route handler validates input with a
zod schema, calls the domain, and shapes the response. No queries, no external
calls, no branching business rules in a handler. Express `req`/`res` (or Fastify
`request`/`reply`) never leave this layer — the domain receives plain typed values.

**`src/api/schemas/` holds zod schemas, one file per scope.** Types are derived
with `z.infer`, so the runtime check and the type cannot drift. Request schemas
are `.strict()`.

**`src/services/` is external I/O and nothing else.** One directory per
upstream. Each service module exposes the pair:

- `call<X>(...)` — performs the request (built-in `fetch` with `AbortSignal.timeout`)
- `condense<X>Response(...)` — validates and strips the upstream envelope at the
  boundary, so callers never see the upstream's wire format

**`src/core/config.ts` owns configuration.** One zod schema parses `process.env`
once at startup and fails fast on missing or invalid values. `process.env`
anywhere else is a defect.

**One response envelope.** Success *and* every error path return the same shape.
One error handler (`app.use((err, req, res, next) => …)` / Fastify
`setErrorHandler`) maps `AppError` subclasses to status codes and the envelope;
unknown errors become a generic 500 with details only in the log.

**`tests/` mirrors `src/`.** `src/services/rag/rag.service.ts` →
`tests/services/rag/rag.service.test.ts`.

**One responsibility per file. One job per function.** Named exports only.

**Names tell the story.** `kebab-case` or `<name>.<role>.ts` filenames (pick the
repo's convention), no `utils.ts` dumping ground, no `tmp`, `data2`, `handleStuff`.

**No dead code.** Delete it. Never leave commented-out blocks behind.

**JSDoc on exported functions/classes** stating *what* and *why*.

## Where does this new file go?

| It … | Put it in |
|------|-----------|
| defines an HTTP endpoint | `src/api/routes/` (versioned subdir if the API is versioned) |
| is a request/response shape | `src/api/schemas/` |
| talks to a third-party or sibling service over the network | `src/services/<upstream>/` |
| encodes a business rule or orchestration | `src/<domain>/` |
| reads env / configures the process | `src/core/config.ts` (extend it) |
| defines error types / maps errors to responses | `src/core/errors.ts` |
| touches the database | `src/core/db/` (`models/`, `queries/`) |
| wraps every request | `src/core/middleware/` |
| is a test | `tests/`, mirroring the source path, `*.test.ts` |

## README standard

See `readme-standard.md`.



## New service scaffold

Minimum viable repo — do not scaffold layers nothing uses yet:

```
src/server.ts  src/app.ts  src/api/routes/  src/api/schemas/envelope.ts
src/core/config.ts  src/core/errors.ts  src/core/logger.ts
tests/  package.json  tsconfig.json  eslint.config.js  vitest.config.ts
README.md  .env.example  Dockerfile  LICENSE  NOTICE  THIRD_PARTY_LICENSES.md  AGENTS.md
```

Minimal `tsconfig.json` compiler options: `"strict": true`,
`"module": "NodeNext"`, `"moduleResolution": "NodeNext"`, `"target": "ES2023"`,
`"noUncheckedIndexedAccess": true`, `"noImplicitOverride": true`,
`"outDir": "dist"`. `package.json`: `"type": "module"`,
`"engines": { "node": ">=24" }`, `"license": "BUSL-1.1"`.

Then run the `onespace-be-busl-licence-compliance` new-repository checklist before the first commit.
