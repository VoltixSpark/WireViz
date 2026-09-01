# -*- coding: utf-8 -*-
"""Session guard: refuse to run against leftover render output.

THE DEFECT THIS PREVENTS

Three tests asserted that an SVG had been inlined into a document. They passed
on the developer's machine and failed in a clean checkout, because what they
were reading was not produced by the test: it was `.svg` and `.bom.tsv` files
left in tests/rendering/ by an earlier local render, gitignored and therefore
invisible to both `git status` and a reviewer.

That is the worst shape a test failure can take. The suite was green precisely
where it should have been red, and the signal only appeared on a machine that
had never rendered anything, which is to say in CI, months later, attached to an
unrelated change.

WHY A GUARD AND NOT A CLEANUP

Deleting the strays automatically would hide the same problem one level down: a
test that depends on generated state would keep depending on it and keep
passing. Failing the whole session states the actual rule, which is that a test
input directory holds inputs. Every test that needs rendered output must render
it into its own tmp_path.

The check compares the directory against git, so it costs nothing in CI (a
fresh checkout has no strays) and fires exactly where the damage happens, on the
machine that has been rendering.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent

# Directories holding hand-authored test INPUTS, which must contain nothing else.
INPUT_DIRS = ("rendering", "bom")

# Extensions the engine emits. A stray one of these is render output, not an
# input, no matter how it got there.
GENERATED_SUFFIXES = {".svg", ".png", ".html", ".tsv", ".gv", ".pdf"}


def _untracked_output(directory: Path) -> list[str]:
    """Files in `directory` that git does not track and that look generated."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(TESTS_DIR), "ls-files", "--others",
             "--", str(directory)],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # No git available (a source tarball, say). The guard is a development
        # aid, not a correctness requirement, so absence of git is not a failure.
        return []

    # --others alone omits gitignored files, which is exactly the case that bit
    # us, so ask for those too and filter to things the engine emits.
    proc_ignored = subprocess.run(
        ["git", "-C", str(TESTS_DIR), "ls-files", "--others", "--ignored",
         "--exclude-standard", "--", str(directory)],
        capture_output=True, text=True, check=False,
    )
    candidates = set(proc.stdout.split()) | set(proc_ignored.stdout.split())
    return sorted(
        f for f in candidates if Path(f).suffix.lower() in GENERATED_SUFFIXES
    )


def pytest_sessionstart(session):
    offenders: list[str] = []
    for name in INPUT_DIRS:
        directory = TESTS_DIR / name
        if directory.is_dir():
            offenders.extend(_untracked_output(directory))

    if not offenders:
        return

    shown = "\n".join(f"    {f}" for f in offenders[:12])
    more = f"\n    ... and {len(offenders) - 12} more" if len(offenders) > 12 else ""
    raise pytest.UsageError(
        f"{len(offenders)} generated file(s) are sitting in the test INPUT "
        f"directories:\n{shown}{more}\n\n"
        f"  These are render output from an earlier local run. A test that reads "
        f"one passes here and fails in a clean checkout, which is how three "
        f"tests stayed green while being broken.\n\n"
        f"  Delete them and re-run:\n"
        f"    git -C {TESTS_DIR.parent} clean -fdX tests/\n\n"
        f"  A test that needs rendered output must render it into its own "
        f"tmp_path, never into the input directory."
    )
