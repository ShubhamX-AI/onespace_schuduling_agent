---
name: busl-licence-compliance
description: >
  Enforces OneSpace BUSL-1.1 licence compliance. Use when creating a new
  repository or service, creating any new source file, adding or upgrading a
  dependency, modifying a file that has no licence header, or when asked to
  "make this repo compliant", "add the licence", "check licensing", or
  "add licence headers". Also use before the first commit of any new repo.
  Carries its own LICENSE/NOTICE templates and an idempotent header script,
  so it works unchanged in any repository it is copied into.
---

# BUSL-1.1 Licence Compliance

OneSpace is licensed under the **Business Source License 1.1 (BUSL-1.1)** — a
source-available licence, not open source. Clients may see, deploy, and modify
the code for their own internal use. They may **not** resell it, white-label it,
or host it as a service for others without a separate commercial agreement with
Indus Net Technologies   (INT).

Every repository, and every source file in it, must carry the notices below.
This is a legal obligation, not a style preference — apply it consistently.

Licence parameters (never alter these):

| Parameter | Value |
|-----------|-------|
| Licensor | Indus Net Technologies   |
| Licensed Work | OneSpace Platform |
| Change Date | Four years from the date of the first public release |
| Change License | Apache License, Version 2.0 |
| Additional Use Grant | Single-instance internal production use; internal modification permitted; no commercial service to third parties, resale, sublicensing, white-labelling, or hosting-as-a-service without a separate commercial licence from INT |
| Commercial enquiries | licensing@intglobal.com |

---

## Step 1 — Root `LICENSE` must exist

Every repository needs a `LICENSE` file at the project root, containing the full
BUSL-1.1 text with the parameters above filled in.

- **Missing?** Copy `templates/LICENSE` from this skill to the repo root.
- **Present?** Treat it as **read-only**. Never delete, rename, or edit it.

Do this before the first commit of a new repo.

## Step 2 — Header on every source file

Every source file carries a copyright and licence notice at the very top, before
any imports or code.

All templates live in `templates/headers.md` (Python, TS/JS, YAML, Dockerfile,
shell, SQL, JSON manifests). Read that file for the exact text.

**Do not paste headers by hand across a repo.** Run the bundled script — it is
idempotent, shebang-aware, and covers every file type:

```bash
# preview
python scripts/add_license_headers.py --root . --dry-run

# apply
python scripts/add_license_headers.py --root .

# CI gate: exit 1 if any file lacks a header
python scripts/add_license_headers.py --root . --check
```

Useful flags: `--exclude 'src/generated/*'` (repeatable) to skip generated trees.

The script already skips `.git`, `.venv`, `node_modules`, `__pycache__`, build
output, and vendored directories.

**Exempt from headers:** test fixtures, seed data, auto-generated files, and
third-party files vendored in unchanged. Mark generated files at the top with
`# AUTO-GENERATED — DO NOT EDIT` — the script detects that marker and skips them.

**Never reword a header.** If the text needs to change, raise it with the tech
lead; it is not an individual decision.

## Step 3 — Declare the licence in the package manifest

Fill in the licence field. Never leave it blank, never use a different identifier.
The only correct value is `BUSL-1.1`.

Pick the form that matches the repo's actual build system — do not add a dead
block for a tool the project does not use.

**Python, PEP 621 (uv / hatch / setuptools / pdm):**

```toml
[project]
name = "onespace-{service-name}"
version = "1.0.0"
license = "BUSL-1.1"
authors = [
    { name = "Indus Net Technologies  ", email = "tech@intglobal.com" },
]

[project.urls]
Homepage = "https://intglobal.com/onespace"
Repository = "<repo url>"
```

**Python, Poetry:**

```toml
[tool.poetry]
name = "onespace-{service-name}"
version = "1.0.0"
license = "BUSL-1.1"
authors = ["Indus Net Technologies   <tech@intglobal.com>"]
homepage = "https://intglobal.com/onespace"
repository = "<repo url>"
```

**Node.js:**

```json
{
  "name": "onespace-{service-name}",
  "version": "1.0.0",
  "license": "BUSL-1.1",
  "author": "Indus Net Technologies  ",
  "homepage": "https://intglobal.com/onespace"
}
```

Replace `{service-name}` with the real service name (e.g. `assist-service`,
`cq-service`).

## Step 4 — Root `NOTICE`

Every repository needs a plain-text `NOTICE` file at the root declaring product,
owner, and contact. Copy `templates/NOTICE` from this skill.

## Step 5 — `THIRD_PARTY_LICENSES.md`

OneSpace depends on open source libraries and is legally required to acknowledge
them. Maintain a `THIRD_PARTY_LICENSES.md` at the repo root. Do not hand-write it
— generate it:

```bash
# Python (uv — no need to add pip-licenses as a project dependency)
uv run --with pip-licenses pip-licenses --format=markdown --with-urls > THIRD_PARTY_LICENSES.md

# Python (pip/poetry env with pip-licenses installed)
pip-licenses --format=markdown > THIRD_PARTY_LICENSES.md

# Node.js
npx license-checker --out THIRD_PARTY_LICENSES.md --markdown
```

**Windows (PowerShell):** `>` writes UTF-16, which corrupts the markdown. Use
`Out-File` and `Select-String` instead:

```powershell
uv run --with pip-licenses pip-licenses --format=markdown --with-urls | Out-File -Encoding utf8 THIRD_PARTY_LICENSES.md
Select-String -Path THIRD_PARTY_LICENSES.md -Pattern '\b(a|l)?gpl' -CaseSensitive:$false
```

Regenerate and commit it **whenever a dependency is added or upgraded**.

**GPL / AGPL is a blocker, not a warning.** After generating, check:

```bash
grep -niE '\b(a|l)?gpl' THIRD_PARTY_LICENSES.md
```

Any GPL or AGPL hit must be raised with the tech lead in `#onespace-dev`
**before merging** — those licences impose obligations on our own code that
conflict with BUSL-1.1. Report LGPL hits too and let the tech lead decide.
Never silently merge past a hit.

## Step 6 — Modifying an existing file

- File already has the correct header? Change nothing. Just write your code.
- File has **no** header (predates this guideline)? Add it as part of your change,
  in a **separate commit**: `chore: add licence header to {filename}`.
  Keeps the functional diff readable.

For a repo-wide first-time sweep, the whole sweep is one isolated commit:
`chore: add BUSL-1.1 licence headers to source files`.

## Step 7 — `README.md` licence section

Every repository's `README.md` ends with a licence section. Copy it from
`templates/README-licence-section.md` and append it at the bottom.

If the README contains a project-structure tree, update that tree to show the new
root files (`LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES.md`) — a stale tree is a
documentation bug.

---

## What NOT to do

- **No other licence identifier.** Not MIT, not Apache-2.0, not ISC, not
  `UNLICENSED`, not blank. Only `BUSL-1.1`.
- **Never skip the header on a new file.** Add it before writing any code.
- **Never copy third-party code in without checking its licence.** A GPL snippet
  pasted from Stack Overflow into an INT file is a legal problem. Ask the tech
  lead first.
- **Never commit a generated file without the `# AUTO-GENERATED — DO NOT EDIT`
  marker.** It keeps the licence audit clean.
- **Never delete or modify `LICENSE`.** It is the legal foundation of every
  client deployment.
- **Never reword a licence header.**

## Quick reference checklist

**New repository**

- [ ] `LICENSE` at root (`templates/LICENSE`)
- [ ] `NOTICE` at root (`templates/NOTICE`)
- [ ] `THIRD_PARTY_LICENSES.md` generated and committed
- [ ] manifest declares `license: BUSL-1.1`
- [ ] `README.md` has the licence section
- [ ] `python scripts/add_license_headers.py --root . --check` exits 0

**New source file**

- [ ] correct header at the top (`templates/headers.md`)
- [ ] manifest updated if this is a new package

**Adding / upgrading a dependency**

- [ ] regenerated `THIRD_PARTY_LICENSES.md`
- [ ] no GPL/AGPL introduced (if yes → stop, raise with tech lead)

**Modifying a header-less file**

- [ ] header added in a separate `chore:` commit

## Who to contact

Ask **before** committing, not after.

- Tech lead — raise in `#onespace-dev`
- External licensing enquiries — licensing@intglobal.com

This skill covers developer obligations only. Client contract clauses and
deployment agreement language are managed by the tech lead and legal team.

---

## Porting this skill to another repository

This skill is self-contained — templates and script travel with it, and nothing
inside it points back at the repo it came from.

1. Copy the whole `busl-licence-compliance/` directory into the target repo's
   `.agents/skills/`.
2. If the target repo uses other agent tools, make the same skill visible to them.
   Symlinking keeps one source of truth:
   ```bash
   mkdir -p .claude/skills .opencode/skills
   ln -s ../../.agents/skills/busl-licence-compliance .claude/skills/busl-licence-compliance
   ln -s ../../.agents/skills/busl-licence-compliance .opencode/skills/busl-licence-compliance
   ```
   Copy the directory instead of symlinking if the toolchain does not follow links
   (accepting that copies drift).
3. Ensure the repo has a root `AGENTS.md` naming this skill as mandatory —
   `.agents/skills/` on its own is passive; an agent has to be told to apply it.
4. Run `python .agents/skills/busl-licence-compliance/scripts/add_license_headers.py --root . --dry-run`
   first, then apply, then work through the new-repository checklist above.
