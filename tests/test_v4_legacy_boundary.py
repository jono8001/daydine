#!/usr/bin/env python3
"""
tests/test_v4_legacy_boundary.py — enforce the V4 ↔ V3.4 import boundary.

No V4 module may import a quarantined V3.4 module except via an
explicit entry in
`operator_intelligence.legacy_boundary.ALLOWED_V4_TO_LEGACY_IMPORTS`.

This test parses each V4 Python file (and the V4 sample runner) using
the stdlib `ast` module and checks every `import` / `from … import`
statement against the registry. It does not execute any of the files
under test, so it cannot be fooled by conditional imports at runtime —
the static surface is what counts.

Run with:
    python -m tests.test_v4_legacy_boundary
"""
from __future__ import annotations

import ast
import os
import sys
import traceback
from typing import Iterable

from operator_intelligence.legacy_boundary import (
    LEGACY_MODULES,
    ALLOWED_V4_TO_LEGACY_IMPORTS,
    SHARED_NARRATIVE_MODULES,
    is_v4_module,
    is_legacy_module,
    is_allowed_v4_to_legacy_import,
)


REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

def _v4_source_files() -> list[tuple[str, str]]:
    """Return list of (importer_dotted_name, abs_path) for every V4
    source file + the sample runner."""
    files: list[tuple[str, str]] = []
    oi = os.path.join(REPO, "operator_intelligence")
    for fname in sorted(os.listdir(oi)):
        if fname.startswith("v4_") and fname.endswith(".py"):
            dotted = f"operator_intelligence.{fname[:-3]}"
            files.append((dotted, os.path.join(oi, fname)))
    # The sample runner is a V4 entry point, too
    files.append((
        "scripts.generate_v4_samples",
        os.path.join(REPO, "scripts", "generate_v4_samples.py"),
    ))
    return files


def _iter_imports(tree: ast.AST) -> Iterable[str]:
    """Yield each imported module name as a dotted string."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.level and node.level > 0:
                # Relative import — not expected in this repo;
                # resolve conservatively to the module name itself.
                yield node.module
            else:
                yield node.module


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_no_v4_file_imports_quarantined_legacy_module():
    violations: list[str] = []
    for importer, path in _v4_source_files():
        with open(path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=path)
            except SyntaxError as e:
                raise AssertionError(f"{path}: syntax error during boundary "
                                     f"check: {e}")
        for imp in _iter_imports(tree):
            if not is_legacy_module(imp):
                continue
            if is_allowed_v4_to_legacy_import(importer, imp):
                continue
            violations.append(
                f"{importer} imports legacy module {imp!r} — either "
                f"remove the import or add it to "
                f"ALLOWED_V4_TO_LEGACY_IMPORTS with a justification "
                f"(see `operator_intelligence/legacy_boundary.py`)."
            )
    _assert(
        not violations,
        "V4 → V3.4 boundary violated:\n  " + "\n  ".join(violations),
    )


def test_every_allowed_v4_to_legacy_entry_is_used():
    """Guard against the allow-list silently accruing stale entries.

    If an entry in ALLOWED_V4_TO_LEGACY_IMPORTS is not actually used,
    the entry is either redundant (remove) or the V4 file was
    refactored to drop the dependency (also remove). Either way the
    entry should be pruned."""
    stale: list[str] = []
    for importer, allowed in ALLOWED_V4_TO_LEGACY_IMPORTS.items():
        # Locate the importer source
        dotted = importer
        rel = dotted.replace(".", os.sep) + ".py"
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            stale.append(
                f"ALLOWED_V4_TO_LEGACY_IMPORTS entry {importer!r} has "
                f"no corresponding source file; remove it."
            )
            continue
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        imports = set(_iter_imports(tree))
        for target in allowed:
            if target not in imports:
                stale.append(
                    f"ALLOWED_V4_TO_LEGACY_IMPORTS says {importer!r} "
                    f"imports {target!r}, but the source file no longer "
                    f"does — remove the allow-list entry."
                )
    _assert(not stale, "\n  ".join(stale))


def test_legacy_and_shared_sets_are_disjoint():
    overlap = LEGACY_MODULES & SHARED_NARRATIVE_MODULES
    _assert(
        not overlap,
        f"LEGACY_MODULES and SHARED_NARRATIVE_MODULES must not overlap; "
        f"shared: {overlap}",
    )


def test_all_legacy_modules_actually_exist():
    missing: list[str] = []
    for dotted in LEGACY_MODULES:
        # Convert dotted to path; packages map to __init__.py
        rel = dotted.replace(".", os.sep)
        path_py = os.path.join(REPO, rel + ".py")
        path_pkg = os.path.join(REPO, rel, "__init__.py")
        if not (os.path.exists(path_py) or os.path.exists(path_pkg)):
            missing.append(dotted)
    _assert(
        not missing,
        f"LEGACY_MODULES entries with no corresponding source: {missing}",
    )


def test_all_shared_modules_actually_exist():
    missing = [
        d for d in SHARED_NARRATIVE_MODULES
        if not os.path.exists(
            os.path.join(REPO, d.replace(".", os.sep) + ".py")
        )
    ]
    _assert(
        not missing,
        f"SHARED_NARRATIVE_MODULES entries with no corresponding source: "
        f"{missing}",
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _collect_tests():
    return [(n, fn) for n, fn in globals().items()
            if n.startswith("test_") and callable(fn)]


def main() -> int:
    failures: list[tuple[str, str]] = []
    for name, fn in _collect_tests():
        try:
            fn()
            print(f"ok   {name}")
        except AssertionError as e:
            failures.append((name, str(e)))
            print(f"FAIL {name} — {e}")
        except Exception as e:
            failures.append((name, f"{type(e).__name__}: {e}"))
            print(f"ERR  {name} — {type(e).__name__}: {e}")
            traceback.print_exc()
    print()
    print(f"Ran {len(_collect_tests())} tests — {len(failures)} failures.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
