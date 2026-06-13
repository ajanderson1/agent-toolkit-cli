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


def build_mcp_rows(
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> list[McpRow]:
    """Build McpRow list from union(library DIRECTORY, scope lock) + filesystem.

    The MCP library is a DIRECTORY (~/.agent-toolkit/mcps/<slug>/), not a lock —
    `mcp add` writes config.json there without touching mcps-lock.json. The
    library half of the universe therefore comes from list_library() (review F1),
    matching `mcp list` (list_cmd.py:86). Source/pin for library/installed rows
    come from the library asset; unlisted rows (lock-only) read the lock entry.

    States: library = in the library dir, not the scope lock; installed = in both;
    unlisted = in the scope lock, not the library dir (warning)."""
    from agent_toolkit_cli.mcp_library import (
        library_root, list_library, load_mcp_asset,
    )
    from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock

    if home is None:
        return []

    library = library_root(home)
    lib_slugs = set(list_library(library))
    scope_lock = (
        read_lock(lock_path_for_scope(scope, home=home, project=project))
        if (scope == "global" or project is not None) else {}
    )
    universe = sorted(lib_slugs | set(scope_lock))

    harnesses = mcp_interactive_harnesses(scope)
    rows: list[McpRow] = []
    for slug in universe:
        in_lib = slug in lib_slugs
        in_lock = slug in scope_lock
        if in_lib and in_lock:
            state: State = "installed"
        elif in_lib:
            state = "library"
        else:
            state = "unlisted"

        # Source/pin: prefer the library asset; fall back to the lock entry for
        # unlisted slugs (no library asset to read).
        source = "unknown"
        pin: str | None = None
        if in_lib:
            try:
                asset = load_mcp_asset(library, slug)
                source = asset.install_method or "unknown"
                pin = asset.resolved_version
            except (FileNotFoundError, ValueError):
                pass
        elif scope_lock.get(slug):
            first = scope_lock[slug][0]
            source, pin = first.source, first.pin

        cells: dict[tuple[str, str], McpCell] = {}
        for harness in harnesses:
            cell = _cell_for(slug, harness, scope=scope, home=home, project=project)
            if cell is not None:
                cells[(harness, scope)] = cell
        rows.append(McpRow(slug=slug, source=source, pin=pin, state=state, cells=cells))
    return rows
