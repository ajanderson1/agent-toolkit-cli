"""`mcp doctor [-g/-p]` — diagnose MCP projection drift. READ-ONLY, never writes.

Per lock entry, three checks:
  1. Orphans / missing — lock entry vs is_installed: a lock entry with no live
     projection is `missing`; a live projection... (orphan entries in the
     config with no lock are surfaced by `mcp list`, not here).
  2. Structural drift — render the library asset through the adapter's
     translate and compare (parsed equality) against the installed entry;
     report `drifted` per (slug, harness).
  3. Env presence — warn on declared env vars (asset.env) absent from
     os.environ. Prints the variable NAME ONLY, never the value (hard security
     constraint).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import click

from agent_toolkit_cli.commands.mcp._common import scope_and_roots, scope_banner
from agent_toolkit_cli.mcp_adapters import get_adapter
from agent_toolkit_cli.mcp_library import (
    McpAsset,
    library_root,
    load_mcp_asset,
)
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock
from agent_toolkit_cli.mcp_standard import mcp_standard_covered


@dataclass
class Finding:
    slug: str
    harness: str
    finding_type: str
    detail: str


def _rendered_entry(harness: str, inner_config: dict) -> dict | None:
    """The harness-native entry the adapter WOULD write for this inner config.

    Re-derives the adapter's translate without writing anything (read-only).
    Returns None if the translate raises (e.g. opencode url source) — the
    caller treats an un-renderable entry as not-drift-checkable.
    """
    from agent_toolkit_cli._install_core import InstallError

    if harness == "codex":
        from agent_toolkit_cli.mcp_adapters.toml_config import _CodexAdapter
        # Symmetry with the JSON branch: codex's _translate cannot raise today,
        # but a future shape-rejecting translate must not crash a read-only
        # doctor — treat an un-renderable entry as not-drift-checkable.
        try:
            return _CodexAdapter()._translate(inner_config)
        except InstallError:
            return None
    from agent_toolkit_cli.mcp_adapters.json_config import CELLS
    cell = CELLS.get(harness)
    if cell is None:
        return None
    try:
        return cell.translate(inner_config)
    except InstallError:
        return None


def _installed_entry(harness: str, slug: str, scope: str, home: Path, project: Path | None) -> dict | None:
    """Read the live installed entry for (slug, harness), parsed. None if absent."""
    adapter = get_adapter(harness)
    try:
        target = adapter.config_target(scope=scope, home=home, project=project)
    except ValueError:
        return None
    if not target.is_file():
        return None
    text = target.read_text(encoding="utf-8")
    if harness == "codex":
        import tomlkit
        try:
            doc = tomlkit.parse(text)
        except Exception:
            return None
        servers = doc.get("mcp_servers")
        if servers is None or slug not in servers:
            return None
        # Unwrap tomlkit items to plain Python for structural comparison.
        return json.loads(json.dumps(servers[slug]))
    try:
        doc = json.loads(text or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(doc, dict):
        return None
    key = "mcp" if harness == "opencode" else "mcpServers"
    servers = doc.get(key)
    if not isinstance(servers, dict) or slug not in servers:
        return None
    return servers[slug]


def _diagnose(
    *, scope: str, home: Path, project: Path | None,
) -> tuple[list[Finding], list[str]]:
    """Return (findings, env_warnings). env_warnings carry NAMES only."""
    findings: list[Finding] = []
    env_warnings: list[str] = []
    library = library_root(home)
    lock = read_lock(lock_path_for_scope(scope, home=home, project=project))

    # Track which slugs we've env-checked so a slug projected into N harnesses
    # warns once per missing var, not N times.
    env_checked: set[str] = set()

    for slug in sorted(lock):
        entries = lock[slug]

        # #399: legacy/partially-collapsed standard de-dup. At project scope, if a
        # slug's rows intersect the covered set {claude-code, pi}, those rows
        # project the same .mcp.json the `standard` row owns (or should own) and
        # must collapse to one `standard` row. Fires on the pure 2-row legacy
        # shape AND the partially-collapsed {standard, pi}/{standard, claude-code}
        # shape (so an orphan covered row is surfaced, not hidden). Read-only:
        # remediation is `mcp install <slug> -p` (collapse-on-install converges it).
        if scope == "project":
            row_harnesses = {e.harness for e in entries}
            if row_harnesses & mcp_standard_covered("project"):
                findings.append(Finding(
                    slug=slug, harness="standard",
                    finding_type="legacy-standard-dedup",
                    detail=(
                        "project lock has claude-code/pi rows for the shared "
                        f".mcp.json; collapse to one `standard` row with "
                        f"`mcp install {slug} -p`"
                    ),
                ))

        try:
            asset: McpAsset | None = load_mcp_asset(library, slug)
        except (FileNotFoundError, ValueError):
            asset = None

        # 3. Env presence (name-only). Declared on the library asset.
        if asset is not None and slug not in env_checked:
            env_checked.add(slug)
            for var in asset.env:
                if var not in os.environ:
                    env_warnings.append(f"env var {var} (declared by {slug}) is not set")

        for entry in sorted(entries, key=lambda e: e.harness):
            harness = entry.harness
            if harness == "standard" and scope != "project":
                # A `standard` row at global scope is structurally invalid (no
                # global standard target); skip the per-entry checks rather than
                # emit a misleading `missing` when config_target raises.
                continue
            adapter = get_adapter(harness)
            try:
                installed = adapter.is_installed(
                    slug, scope=scope, home=home, project=project
                )
            except ValueError:
                installed = False

            # 1. Missing projection: lock says installed, config does not.
            if not installed:
                findings.append(Finding(
                    slug=slug, harness=harness, finding_type="missing",
                    detail="lock entry exists but no live projection in the harness config",
                ))
                continue

            # 2. Structural drift: rendered library entry vs installed entry.
            if asset is None:
                findings.append(Finding(
                    slug=slug, harness=harness, finding_type="orphan-library",
                    detail="projected + locked but the library entry is missing/unreadable",
                ))
                continue
            rendered = _rendered_entry(harness, asset.inner_config)
            installed_entry = _installed_entry(harness, slug, scope, home, project)
            if rendered is None or installed_entry is None:
                # Cannot compare (un-renderable, e.g. opencode url) — skip drift,
                # best-effort per the spec's pragmatic allowance.
                continue
            if _normalise(rendered) != _normalise(installed_entry):
                findings.append(Finding(
                    slug=slug, harness=harness, finding_type="drifted",
                    detail="installed entry differs structurally from the library source",
                ))

    return findings, env_warnings


def _normalise(value: object) -> object:
    """Round-trip through JSON to strip tomlkit/ordering artifacts for an
    order-insensitive structural comparison of dict values."""
    return json.loads(json.dumps(value, sort_keys=True))


@click.command("doctor")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def doctor_cmd(
    ctx: click.Context,
    global_: bool,
    project_flag: bool,
) -> None:
    """Diagnose MCP projection drift (read-only — never writes)."""
    scope, home, project_root, implicit = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    effective_home = home if home is not None else Path.home()
    # doctor has no body-level lock read (the lock is read inside _diagnose), so
    # read it here purely for the banner count, mirroring agent/skill doctor.
    # mcp_lock.read_lock returns {} on a missing file (safe at implicit-global)
    # and raises only on a malformed lock; on the implicit-project path the lock
    # is toolkit-written and well-formed.
    lock_path = lock_path_for_scope(scope, home=effective_home, project=project_root)
    scope_banner(
        scope, implicit=implicit, lock_path=lock_path, count=len(read_lock(lock_path))
    )
    findings, env_warnings = _diagnose(
        scope=scope, home=effective_home, project=project_root,
    )

    for w in env_warnings:
        click.echo(f"WARNING: {w}")

    if not findings:
        if env_warnings:
            click.echo(f"no projection drift ({len(env_warnings)} env warning(s))")
        else:
            click.echo("all clean")
        return

    for f in findings:
        click.echo(f"{f.slug} · {f.harness} · {f.finding_type} ({scope})")
        click.echo(f"  detail: {f.detail}")

    click.echo("")
    click.echo(f"summary: {len(findings)} finding(s), {len(env_warnings)} env warning(s)")
    ctx.exit(1)
