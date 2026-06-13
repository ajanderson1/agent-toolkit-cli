"""Shared helpers for the mcp command group.

MCP scope-resolution fork: scope_and_roots is identical to
commands/agent/_common.py's version EXCEPT the "project lock present?" probe
keys off mcp_lock.LOCK_FILENAME (mcps-lock.json), not agents-lock.json. The
fork is required, not delegatable — the agent version hard-codes the wrong
lockfile, which would default the MCP read-verb scope off the wrong file.

parse_harness_tokens is deliberately NOT ported: that is agent-specific
synthetic-harness logic with `standard` normalization. MCP harnesses are
claude-code/codex/opencode/pi with no synthetic names; MCP harness-token
parsing, if needed, belongs in the CLI (Task 8), not here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import click

from agent_toolkit_cli import mcp_lock

_LOCK_FILENAME = mcp_lock.LOCK_FILENAME

Scope = Literal["project", "global"]

# The four MCP-capable harnesses, in adapter-registry order. Shared by every
# write verb that fans out to "all harnesses" by default. SSOT for the
# --harness click.Choice and the no-flag install default.
_HARNESSES: tuple[str, ...] = ("claude-code", "codex", "opencode", "pi")


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[Scope, Path | None, Path | None]:
    """Resolve (scope, home, project_root) from CLI flags + context.

    Convention (cross-cutting, verified):
      - READ verbs pass read_only=True so they default to global outside a
        project (no mcps-lock.json in cwd). This avoids a confusing
        "lock not found" error when the user runs `mcp list` from their
        home directory.
      - WRITE verbs do NOT pass read_only; they default to project scope so
        the consumer project is the implicit target.
    """
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / _LOCK_FILENAME).exists():
        return "global", Path.home(), None
    return "project", None, project_root
