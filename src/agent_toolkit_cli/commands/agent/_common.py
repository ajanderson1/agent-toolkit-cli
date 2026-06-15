"""Shared helpers for the agent command group.

scope_and_roots is parametrised on AGENT_BINDING.lock_filename
(agents-lock.json), mirroring commands/pi_extension/_common.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import click

from agent_toolkit_cli._paths_core import AGENT_BINDING

_LOCK_FILENAME = AGENT_BINDING.lock_filename

Scope = Literal["project", "global"]

# Synthetic catalog names (#361 AC7): real AGENTS entries that are NOT
# installable harnesses for the agent asset type. Rejected with an explicit
# UsageError instead of the previous silent no-op.
_SYNTHETIC_HARNESS_TOKENS = frozenset({"standard-skill", "standard-agent"})


def parse_harness_tokens(harnesses_str: str) -> tuple[str, ...]:
    """Parse an explicit --harnesses value into validated harness names.

    Shared by install and uninstall: rejects the
    synthetic catalog names, normalizes claude-code → standard (claude-code's
    destination IS the standard slot at both scopes; one slot, one token —
    prevents a dual-name delta where plan() removes one alias while
    installing the other), validates against the catalog, and dedupes
    preserving order.
    """
    from agent_toolkit_cli.skill_agents import AGENTS

    parts = [p.strip() for p in harnesses_str.split(",") if p.strip()]
    synthetic = [p for p in parts if p in _SYNTHETIC_HARNESS_TOKENS]
    if synthetic:
        raise click.UsageError(
            f"synthetic catalog name(s): {', '.join(synthetic)}; use 'standard'"
        )
    parts = ["standard" if p == "claude-code" else p for p in parts]
    unknown = [p for p in parts if p not in AGENTS]
    if unknown:
        raise click.UsageError(f"unknown harness(es): {', '.join(unknown)}")
    seen: set[str] = set()
    deduped: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return tuple(deduped)


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[Scope, Path | None, Path | None, bool]:
    """Resolve (scope, home, project_root, implicit) from CLI flags + context.

    ``implicit`` is True iff neither -g nor -p was passed — i.e. the scope was
    inferred from the presence/absence of <cwd>/agents-lock.json. Read verbs use
    it to decide whether to print a scope reminder (#418, mirrors #413).

    Convention (cross-cutting, verified):
      - READ verbs pass read_only=True so they default to global outside a
        project (no agents-lock.json in cwd). This avoids a confusing
        "lock not found" error when the user runs `agent list` from their
        home directory.
      - WRITE verbs do NOT pass read_only; they default to project scope so
        the consumer project is the implicit target.
    """
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None, False
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root, False
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / _LOCK_FILENAME).exists():
        return "global", Path.home(), None, True
    return "project", None, project_root, True


def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Print a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project — the one case (#418, mirrors #413) where the user got no signal
    about which lock was picked. Goes to stdout by default (so a human sees it
    inline with the verb output); callers emitting a machine stream pass
    ``err=True`` to route it to stderr instead (today only ``list --json``).
    """
    if not (implicit and scope == "project"):
        return
    noun = "agent" if count == 1 else "agents"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
