# Licence header templates

Copy verbatim. The header goes at the **very top** of the file, before any imports
or code — except after a `#!` shebang line or a PEP 263 `# -*- coding: -*-` line,
which must stay on lines 1–2.

Do not reword these. If the text needs to change, raise it with the tech lead.

`scripts/add_license_headers.py` applies every template below automatically.
Use the script rather than pasting by hand — it is idempotent and shebang-aware.

---

## Python (`.py`)

```python
# Copyright (c) 2026 Indus Net Technologies  
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
```

## TypeScript / JavaScript (`.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`)

```javascript
/**
 * Copyright (c) 2026 Indus Net Technologies  
 * Licensed under the Business Source License 1.1 (BUSL-1.1)
 * See LICENSE file in the project root for full licence terms.
 * Additional Use Grant: internal deployment and modification only.
 * Commercial licensing: licensing@intglobal.com
 */
```

## YAML (`.yaml`, `.yml`)

```yaml
# Copyright (c) 2026 Indus Net Technologies  
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE in the project root for terms.
```

## Dockerfile

```dockerfile
# Copyright (c) 2026 Indus Net Technologies  
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE in the project root for terms.
```

## Shell scripts (`.sh`)

```bash
#!/bin/bash
# Copyright (c) 2026 Indus Net Technologies  
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE in the project root for terms.
```

## SQL migrations (`.sql`)

```sql
-- Copyright (c) 2026 Indus Net Technologies  
-- Licensed under the Business Source License 1.1 (BUSL-1.1)
-- See LICENSE in the project root for terms.
```

## JSON (`.json`)

JSON has no comment syntax. For a **configuration manifest** (e.g. `package.json`),
declare the licence as a field instead:

```json
{
  "license": "BUSL-1.1"
}
```

For **data files**, add nothing — the root `LICENSE` file covers them.

---

## Files that need no header

- test fixtures and seed data
- auto-generated files — instead mark them clearly at the top:
  `# AUTO-GENERATED — DO NOT EDIT`
- third-party files vendored in unchanged (keep their original licence text intact)
- config manifests and dotfiles — licence is declared via the manifest's
  `license` field (Step 3 of SKILL.md) or the root `LICENSE`, not a header:
  `pyproject.toml`, `package.json`, `.env.example`, `.dockerignore`,
  `.python-version`, `.gitignore`, and similar dotfiles

The script applies this automatically: files whose type has no header mapping
(TOML, dotfiles, etc.) are never flagged by `--check`.
