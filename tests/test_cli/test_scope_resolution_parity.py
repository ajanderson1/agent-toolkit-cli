"""#427 — cross-kind parity guard for ``scope_and_roots``.

The four asset types (skill / agent / mcp / pi-extension) each keep their own
copy of ``scope_and_roots`` in ``commands/<kind>/_common.py`` (#427 decision:
KEEP the copies, do not unify). The copies are byte-identical except the lock
filename, and the implicit-scope feature (#413) depends on all four resolving
scope *identically*. This test is the durable guard against one copy silently
drifting from the others: it asserts every kind produces the structurally
identical 4-tuple ``(scope, home, project_root, implicit)`` for the same
(flags, cwd, lock-present?) matrix, and raises identically when both flags are
passed.

It reads each kind's lock filename from the authoritative source (the
``_paths_core`` binding, or ``mcp_lock.LOCK_FILENAME`` for mcp) so the test
tracks the real discriminator rather than a hardcoded literal.
"""
from __future__ import annotations

from pathlib import Path

import click
import pytest

from agent_toolkit_cli import mcp_lock
from agent_toolkit_cli._paths_core import (
    AGENT_BINDING,
    PI_EXTENSION_BINDING,
    SKILL_BINDING,
)
from agent_toolkit_cli.commands.agent._common import scope_and_roots as agent_sar
from agent_toolkit_cli.commands.mcp._common import scope_and_roots as mcp_sar
from agent_toolkit_cli.commands.pi_extension._common import (
    scope_and_roots as pi_sar,
)
from agent_toolkit_cli.commands.skill._common import scope_and_roots as skill_sar

# (label, resolver, lock_filename) — one entry per asset type.
KINDS = [
    ("skill", skill_sar, SKILL_BINDING.lock_filename),
    ("agent", agent_sar, AGENT_BINDING.lock_filename),
    ("mcp", mcp_sar, mcp_lock.LOCK_FILENAME),
    ("pi-extension", pi_sar, PI_EXTENSION_BINDING.lock_filename),
]


def _expected(row: str, tmp_path: Path) -> tuple[str, Path | None, Path | None, bool]:
    """The structurally-identical 4-tuple every kind must return for ``row``."""
    return {
        "explicit_global": ("global", Path.home(), None, False),
        "explicit_project": ("project", None, tmp_path, False),
        "implicit_global_readonly_no_lock": ("global", Path.home(), None, True),
        "implicit_project_readonly_lock": ("project", None, tmp_path, True),
        "implicit_project_write": ("project", None, tmp_path, True),
    }[row]


@pytest.mark.parametrize(
    ("row", "global_", "project", "read_only", "seed_lock"),
    [
        ("explicit_global", True, False, True, False),
        ("explicit_project", False, True, True, False),
        ("implicit_global_readonly_no_lock", False, False, True, False),
        ("implicit_project_readonly_lock", False, False, True, True),
        ("implicit_project_write", False, False, False, False),
    ],
)
def test_all_kinds_resolve_identically(
    row: str,
    global_: bool,
    project: bool,
    read_only: bool,
    seed_lock: bool,
    tmp_path: Path,
) -> None:
    """Every kind returns the same 4-tuple for the same (flags, cwd, lock?) row."""
    expected = _expected(row, tmp_path)
    results: list[tuple[str, tuple[str, Path | None, Path | None, bool]]] = []
    for label, resolver, lock_filename in KINDS:
        if seed_lock:
            (tmp_path / lock_filename).write_text("{}\n", encoding="utf-8")
        actual = resolver(global_, project, tmp_path, read_only=read_only)
        if seed_lock:
            (tmp_path / lock_filename).unlink()
        # Each kind matches the expected tuple...
        assert actual == expected, f"{label} diverged on row {row}: {actual!r}"
        results.append((label, actual))
    # ...and every kind agrees with every other (the parity assertion).
    first_label, first = results[0]
    for label, actual in results[1:]:
        assert actual == first, (
            f"resolver parity broken on row {row}: "
            f"{label}={actual!r} vs {first_label}={first!r}"
        )


def test_all_kinds_reject_both_flags(tmp_path: Path) -> None:
    """Passing both -g and -p raises UsageError in every kind, identically."""
    for label, resolver, _lock in KINDS:
        with pytest.raises(click.UsageError, match="not both"):
            resolver(True, True, tmp_path, read_only=True)
