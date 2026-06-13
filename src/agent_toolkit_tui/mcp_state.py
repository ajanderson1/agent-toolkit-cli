"""Data model for the TUI's MCP tab.

Reads the MCP lock + filesystem to produce McpRow records with per-harness
cell state. Mirrors agent_state.py for the MCP asset type, with two MCP-specific
differences:

- Columns are scope-dependent and NOT a frozen module constant. The standard
  projection (#399) exists only at PROJECT scope (covered set {claude-code, pi}).
  mcp_standard_covered('global') raises KeyError; the grid derives the harness
  tuple per scope via mcp_interactive_harnesses(scope).
- Linked = the named entry is present in the harness's config file, probed via
  the MCP adapter's is_installed() — NOT adapter.destination().exists() (MCP is
  config-injection by name, not a file/symlink).

Row-universe contract: union(library lock, scope lock) — canonical statement in
skill_state.py's docstring. Rows carry a `state`: `installed` (in the scope
lock), `library` (library-only), `unlisted` (scope-lock-only, warning).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.mcp_adapters import get_adapter
from agent_toolkit_tui.composition import mcp_nonstandard_main

Scope = Literal["global", "project"]
State = Literal["installed", "library", "unlisted"]


def mcp_interactive_harnesses(scope: str) -> tuple[str, ...]:
    """Rendered harness columns for `scope`: the standard slot first (project
    only), then the non-covered MCP harnesses. Derived per scope — never a
    frozen constant — because the column set differs by scope (no standard at
    global)."""
    nonstandard = mcp_nonstandard_main(scope)
    if scope == "project":
        return ("standard",) + nonstandard
    return nonstandard


@dataclass(frozen=True)
class McpCell:
    """Per-(harness, scope) install state for a single MCP slug."""

    linked: bool  # the named entry exists in the harness config at this scope


@dataclass
class McpRow:
    """One row per slug in union(library lock, scope lock)."""

    slug: str
    source: str            # install_method: npx | uvx | docker | url | local
    pin: str | None = None
    state: State = "installed"
    cells: dict[tuple[str, str], McpCell] = field(default_factory=dict)


def _cell_for(
    slug: str,
    harness_name: str,
    *,
    scope: Scope,
    home: Path,
    project: Path | None,
) -> McpCell | None:
    """Return McpCell for a (slug, harness, scope) triple, or None if the
    harness has no adapter / is not installable at this scope.

    Returns None when:
    - get_adapter() raises (unknown harness → UnsupportedMcpHarnessError, an
      InstallError).
    - the adapter's is_installed() raises (scope mismatch, e.g. the standard
      adapter at global scope — there is no global .mcp.json target — raises
      InstallError; a ValueError is also tolerated).

    Otherwise McpCell(linked=is_installed(...))."""
    try:
        adapter = get_adapter(harness_name)
    except (InstallError, ValueError):
        return None
    try:
        linked = adapter.is_installed(slug, scope=scope, home=home, project=project)
    except (InstallError, ValueError):
        return None
    return McpCell(linked=linked)
