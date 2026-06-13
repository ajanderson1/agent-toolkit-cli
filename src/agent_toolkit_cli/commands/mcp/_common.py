"""Shared helpers for the mcp command group.

MCP scope-resolution fork: scope_and_roots is identical to
commands/agent/_common.py's version EXCEPT the "project lock present?" probe
keys off mcp_lock.LOCK_FILENAME (mcps-lock.json), not agents-lock.json. The
fork is required, not delegatable — the agent version hard-codes the wrong
lockfile, which would default the MCP read-verb scope off the wrong file.

normalize_harness_tokens IS now ported (#399) but as a SCOPE-AWARE normalizer
(NOT named parse_harness_tokens — MCP uses a repeatable --harness flag, so it
takes an already-split tuple, not a comma string). At PROJECT scope `claude-code`
and `pi` both normalize to `standard` (the shared <project>/.mcp.json IS the
standard slot — see mcp_standard.py); at GLOBAL scope there is NO standard (no
`~/.mcp.json` reader), so they pass through unchanged and a `standard` token is
rejected. This reverses the prior "deliberately not ported" decision: the project
`.mcp.json` genuinely is a standard slot, it is just project-scoped.
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

# The --harness Choice universe: the four concrete harnesses + the synthetic
# `standard` token. Validation is permissive here; normalize_harness_tokens and
# the adapter enforce the scope rules (standard is project-only).
_CHOICE_HARNESSES: tuple[str, ...] = (*_HARNESSES, "standard")


def default_harnesses(scope: str) -> tuple[str, ...]:
    """The no-flag install target set, scope-aware.

    Project: `standard` (covers claude-code+pi via the shared .mcp.json) plus the
    genuine outliers codex (TOML) and opencode (`mcp` key) — one .mcp.json write,
    no double-write. Global: the concrete four (no standard exists globally)."""
    if scope == "project":
        return ("standard", "codex", "opencode")
    return _HARNESSES


def normalize_harness_tokens(tokens: tuple[str, ...], *, scope: str) -> tuple[str, ...]:
    """Normalize explicit --harness tokens, scope-aware, order-preserving + deduped.

    Project: claude-code → standard, pi → standard (the shared .mcp.json is the
    standard slot). Global: no normalization; a `standard` token is rejected
    (there is no global standard). Mirrors commands/agent/_common.py but on the
    already-split tuple (MCP uses a repeatable --harness flag, not a comma string)
    and with the project/global asymmetry the agent kind lacks."""
    if scope == "project":
        mapped = ["standard" if t in ("claude-code", "pi") else t for t in tokens]
    else:
        if "standard" in tokens:
            raise click.UsageError(
                "standard is a project-scope projection; it has no global target "
                "(no client reads ~/.mcp.json). Use -p, or name a concrete harness."
            )
        mapped = list(tokens)
    seen: set[str] = set()
    out: list[str] = []
    for t in mapped:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return tuple(out)


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
