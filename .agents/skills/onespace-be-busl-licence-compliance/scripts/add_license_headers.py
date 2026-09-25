#!/usr/bin/env python3
# Copyright (c) 2026 Indus Net Technologies  
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Add BUSL-1.1 licence headers to source files.

Idempotent: a file already carrying the licence marker is left untouched, so the
script is safe to re-run and safe to wire into CI via --check.

Usage:
    python add_license_headers.py                 # write headers under CWD
    python add_license_headers.py --root path     # write headers under path
    python add_license_headers.py --dry-run       # list what would change
    python add_license_headers.py --check         # exit 1 if any file lacks a header
    python add_license_headers.py --exclude 'src/generated/*' --exclude '*_pb2.py'

Stdlib only, no dependencies — copy it into any repo alongside the skill.
"""

import argparse
import fnmatch
import sys
from pathlib import Path

# Any file containing this string near the top is considered already headered.
MARKER = "Business Source License 1.1"

# Files carrying this marker are generated and exempt from headers.
GENERATED_MARKER = "AUTO-GENERATED"

# Never walk into these directory names.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    ".tox",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "site",
    "dist",
    "build",
    "logs",
    ".idea",
    ".vscode",
    "vendor",
    "third_party",
    "migrations_vendored",
    "development_docs",
    ".egg-info",
}

_FULL = [
    "Copyright (c) 2026 Indus Net Technologies  ",
    "Licensed under the Business Source License 1.1 (BUSL-1.1)",
    "See LICENSE file in the project root for full licence terms.",
    "Additional Use Grant: internal deployment and modification only.",
    "Commercial licensing: licensing@intglobal.com",
]

_SHORT = [
    "Copyright (c) 2026 Indus Net Technologies  ",
    "Licensed under the Business Source License 1.1 (BUSL-1.1)",
    "See LICENSE in the project root for terms.",
]


def _hash_header(lines: list[str]) -> str:
    """Render a header as `#`-comment lines."""
    return "".join(f"# {line}\n" for line in lines)


def _dash_header(lines: list[str]) -> str:
    """Render a header as SQL `--`-comment lines."""
    return "".join(f"-- {line}\n" for line in lines)


def _block_header(lines: list[str]) -> str:
    """Render a header as a `/** ... */` block comment."""
    body = "".join(f" * {line}\n" for line in lines)
    return f"/**\n{body} */\n"


# Extension -> rendered header. Extensions are matched case-insensitively.
HEADERS: dict[str, str] = {
    ".py": _hash_header(_FULL),
    ".ts": _block_header(_FULL),
    ".tsx": _block_header(_FULL),
    ".js": _block_header(_FULL),
    ".jsx": _block_header(_FULL),
    ".mjs": _block_header(_FULL),
    ".cjs": _block_header(_FULL),
    ".yaml": _hash_header(_SHORT),
    ".yml": _hash_header(_SHORT),
    ".sh": _hash_header(_SHORT),
    ".bash": _hash_header(_SHORT),
    ".sql": _dash_header(_SHORT),
}

# Filenames (not extensions) that get the short hash header.
FILENAME_HEADERS: dict[str, str] = {
    "dockerfile": _hash_header(_SHORT),
}


def header_for(path: Path) -> str | None:
    """Return the header text for this file, or None if the type is exempt."""
    name = path.name.lower()
    if name in FILENAME_HEADERS:
        return FILENAME_HEADERS[name]
    # Dockerfile.prod, Dockerfile.uat, ...
    if name.startswith("dockerfile"):
        return FILENAME_HEADERS["dockerfile"]
    return HEADERS.get(path.suffix.lower())


def is_headered(text: str) -> bool:
    """True if the licence marker appears in the first 15 lines."""
    return MARKER in "\n".join(text.splitlines()[:15])


def is_generated(text: str) -> bool:
    """True if the file is marked auto-generated in its first 15 lines."""
    return GENERATED_MARKER in "\n".join(text.splitlines()[:15])


def insert_header(text: str, header: str) -> str:
    """Insert the header at the top, after a shebang or encoding line if present."""
    lines = text.splitlines(keepends=True)
    at = 0
    # A shebang must stay on line 1.
    if lines and lines[0].startswith("#!"):
        at = 1
        # PEP 263 encoding declarations must stay within the first two lines.
        if len(lines) > 1 and "coding" in lines[1] and lines[1].lstrip().startswith("#"):
            at = 2
    elif lines and "coding" in lines[0] and lines[0].lstrip().startswith("#"):
        at = 1
    return "".join(lines[:at]) + header + "".join(lines[at:])


def iter_candidates(root: Path, excludes: list[str]):
    """Yield every file under root whose type needs a licence header."""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in rel.parts):
            continue
        posix = rel.as_posix()
        if any(fnmatch.fnmatch(posix, pat) or fnmatch.fnmatch(path.name, pat) for pat in excludes):
            continue
        if header_for(path) is None:
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Add BUSL-1.1 licence headers to source files.")
    parser.add_argument("--root", default=".", help="repo root to walk (default: CWD)")
    parser.add_argument("--dry-run", action="store_true", help="list files that would change")
    parser.add_argument("--check", action="store_true", help="exit 1 if any file lacks a header")
    parser.add_argument("--exclude", action="append", default=[], help="glob to skip (repeatable)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    missing: list[Path] = []
    changed: list[Path] = []
    skipped_generated: list[Path] = []

    for path in iter_candidates(root, args.exclude):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            print(f"skip (unreadable): {path.relative_to(root)} — {exc}", file=sys.stderr)
            continue

        if is_headered(text):
            continue
        if is_generated(text):
            skipped_generated.append(path)
            continue

        missing.append(path)
        if args.check or args.dry_run:
            continue

        path.write_text(insert_header(text, header_for(path)), encoding="utf-8")
        changed.append(path)

    for path in skipped_generated:
        print(f"exempt (auto-generated): {path.relative_to(root)}")

    if args.check:
        for path in missing:
            print(f"missing header: {path.relative_to(root)}")
        print(f"{len(missing)} file(s) missing a licence header")
        return 1 if missing else 0

    if args.dry_run:
        for path in missing:
            print(f"would add header: {path.relative_to(root)}")
        print(f"{len(missing)} file(s) would change")
        return 0

    for path in changed:
        print(f"added header: {path.relative_to(root)}")
    print(f"{len(changed)} file(s) changed")
    return 0


def _self_check() -> None:
    """Assert the tricky bits: shebang order, idempotency, per-type rendering."""
    py = HEADERS[".py"]

    # Shebang stays on line 1.
    out = insert_header("#!/bin/bash\necho hi\n", HEADERS[".sh"])
    assert out.startswith("#!/bin/bash\n"), out
    assert MARKER in out.splitlines()[2], out

    # No shebang: header goes first.
    out = insert_header("import os\n", py)
    assert out.startswith("# Copyright"), out
    assert out.endswith("import os\n"), out

    # Encoding line stays within the first two lines.
    out = insert_header("#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nx = 1\n", py)
    lines = out.splitlines()
    assert lines[0].startswith("#!") and "coding" in lines[1], out

    # Idempotency: a headered file is recognised and never re-headered.
    assert is_headered(insert_header("import os\n", py))
    assert not is_headered("import os\n")

    # Generated files are detected.
    assert is_generated("# AUTO-GENERATED — DO NOT EDIT\nx = 1\n")

    # Per-type comment syntax.
    assert HEADERS[".sql"].startswith("-- Copyright")
    assert HEADERS[".ts"].startswith("/**\n") and HEADERS[".ts"].rstrip().endswith("*/")
    assert header_for(Path("Dockerfile")) and header_for(Path("Dockerfile.prod"))
    assert header_for(Path("data.json")) is None

    # Empty file still gets a header.
    assert insert_header("", py) == py
    print("self-check ok")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        _self_check()
    else:
        raise SystemExit(main())
