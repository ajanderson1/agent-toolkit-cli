"""`mcp list [-g/-p]` — library inventory + per-harness projection state.

Read-only: defaults to global outside a project. For each library slug shows
its resolved version (or `floating`), and per harness whether it is installed
at the resolved scope. When a locked pin LAGS the library's resolved_version
the lag is flagged `<pin> (library: <version> — stale)`. Unmanaged entries
(present in a harness config but not in our lock) are SURFACED — visible,
never touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from agent_toolkit_cli.commands.mcp._common import _HARNESSES, scope_and_roots
from agent_toolkit_cli.mcp_adapters import get_adapter
from agent_toolkit_cli.mcp_library import library_root, list_library, load_mcp_asset
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock


def _servers_in_config(harness: str, scope: str, home: Path, project: Path | None) -> set[str]:
    """Enumerate the MCP entry names present in a harness's config (best-effort).

    Used to surface UNMANAGED entries — those not in our lock. Returns an empty
    set on any read/parse failure (a broken config must not crash a read verb).
    """
    adapter = get_adapter(harness)
    try:
        target = adapter.config_target(scope=scope, home=home, project=project)
    except ValueError:
        return set()
    if not target.is_file():
        return set()
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return set()
    if harness == "codex":
        import tomlkit
        try:
            doc = tomlkit.parse(text)
        except Exception:
            return set()
        servers = doc.get("mcp_servers")
        return set(servers.keys()) if servers is not None else set()
    # JSON family: claude-code / pi (mcpServers), opencode (mcp).
    try:
        doc = json.loads(text or "{}")
    except json.JSONDecodeError:
        return set()
    if not isinstance(doc, dict):
        return set()
    key = "mcp" if harness == "opencode" else "mcpServers"
    servers = doc.get(key)
    return set(servers.keys()) if isinstance(servers, dict) else set()


@click.command("list", epilog="""\
Examples:

\b
  agent-toolkit-cli mcp list           # default scope
  agent-toolkit-cli mcp list -g        # global
  agent-toolkit-cli mcp list -p        # project
""")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def list_cmd(
    ctx: click.Context,
    global_: bool,
    project_flag: bool,
) -> None:
    """List library MCPs with per-harness projection state."""
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    effective_home = home if home is not None else Path.home()
    library = library_root(Path.home())
    lock = read_lock(lock_path_for_scope(scope, home=effective_home, project=project_root))

    slugs = list_library(library)
    if not slugs and not lock:
        click.echo("no MCP servers in the library")
        # Still fall through to the unmanaged scan below — a user may have
        # hand-rolled entries with an empty library.

    for slug in slugs:
        try:
            asset = load_mcp_asset(library, slug)
        except (FileNotFoundError, ValueError):
            click.echo(f"{slug}\t(library entry unreadable)")
            continue
        version = asset.resolved_version or "floating"
        click.echo(f"{slug}\t{version}")
        locked = {e.harness: e for e in lock.get(slug, [])}
        for harness in _HARNESSES:
            adapter = get_adapter(harness)
            try:
                installed = adapter.is_installed(
                    slug, scope=scope, home=effective_home, project=project_root
                )
            except ValueError:
                installed = False
            mark = "✔" if installed else "☐"
            note = ""
            entry = locked.get(harness)
            if (
                entry is not None
                and entry.pin is not None
                and asset.resolved_version is not None
                and entry.pin != asset.resolved_version
            ):
                note = f"  {entry.pin} (library: {asset.resolved_version} — stale)"
            click.echo(f"  {mark} {harness}{note}")

    # Surface unmanaged entries: anything in a harness config NOT tracked by
    # our lock. Visible, never touched.
    #
    # Shared-file de-dup (spec §"Pi project scope and claude-code project scope
    # write the SAME file"): several harnesses can resolve to the SAME config
    # file (pi + claude-code both target <project>/.mcp.json at project scope).
    # An entry we manage there for claude-code is NOT unmanaged-for-pi just
    # because it isn't tracked under pi's harness name. So an entry is "managed"
    # for a file if it is tracked for ANY harness whose config_target resolves to
    # that same file path — we group the lock's tracked slugs by resolved path and
    # subtract the union, not just the per-harness set.
    tracked_by_path: dict[Path, set[str]] = {}
    for harness in _HARNESSES:
        adapter = get_adapter(harness)
        try:
            path = adapter.config_target(
                scope=scope, home=effective_home, project=project_root
            )
        except ValueError:
            continue
        slugs_for_harness = {
            slug
            for slug, entries in lock.items()
            if any(e.harness == harness for e in entries)
        }
        tracked_by_path.setdefault(path.resolve(), set()).update(slugs_for_harness)

    for harness in _HARNESSES:
        adapter = get_adapter(harness)
        try:
            path = adapter.config_target(
                scope=scope, home=effective_home, project=project_root
            )
        except ValueError:
            continue
        present = _servers_in_config(harness, scope, effective_home, project_root)
        managed = tracked_by_path.get(path.resolve(), set())
        for name in sorted(present - managed):
            click.echo(f"[!] unmanaged: {name} ({harness})")
