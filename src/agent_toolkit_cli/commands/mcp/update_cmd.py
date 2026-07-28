"""`mcp update <slug>` — re-resolve manifest authority and re-project.

The global manifest is committed first, then its config/sidecar pair is
materialised, then every reachable locked projection is refreshed. Legacy
libraries must be adopted explicitly with ``mcp migrate``.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import click

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.commands.mcp import _resolve
from agent_toolkit_cli.commands.mcp._common import _LOCK_FILENAME, normalize_harness_tokens
from agent_toolkit_cli.mcp_adapters import UnsupportedMcpHarnessError
from agent_toolkit_cli.mcp_library import (
    library_root,
    materialize_entry,
    scan_entry_files,
)
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock
from agent_toolkit_cli.mcp_manifest import (
    McpManifestEntry,
    manifest_path,
    read_manifest,
    write_manifest,
)


def _reresolve(
    entry: McpManifestEntry, slug: str
) -> tuple[McpManifestEntry, str | None]:
    """Return a freshly resolved immutable entry plus an optional note."""
    new_version: str | None
    if entry.install_method == "npx":
        new_version = _resolve.resolve_npm_version(entry.source)
        if new_version is None:
            return entry, None
        args = list(entry.args)
        args[-1] = f"{entry.source}@{new_version}"
        return replace(entry, args=tuple(args), resolved_version=new_version), None
    if entry.install_method == "uvx":
        new_version = _resolve.resolve_pypi_version(entry.source)
        if new_version is None:
            return entry, None
        args = list(entry.args)
        args[-1] = f"{entry.source}=={new_version}"
        return replace(entry, args=tuple(args), resolved_version=new_version), None
    if entry.install_method == "local":
        new_version = _resolve.resolve_git_head_sha(Path(entry.source))
        if new_version is None:
            return entry, (
                f"note: {slug} source directory is missing or not a git repo; "
                "cannot refresh SHA"
            )
        return replace(entry, resolved_version=new_version), None
    # Docker tags are already the version authority; URLs have no version.
    return entry, None


@click.command("update", epilog="""\
Examples:

\b
  agent-toolkit-cli mcp update context7
""")
@click.argument("slug")
@click.pass_context
def update_cmd(ctx: click.Context, slug: str) -> None:
    """Re-resolve a library MCP and re-project every reachable locked harness."""
    home = Path.home()
    library = library_root(home)
    path = manifest_path(home)
    if not path.is_file():
        if scan_entry_files(library):
            raise click.ClickException(
                "MCP library manifest is missing; run: "
                "agent-toolkit-cli mcp migrate"
            )
        raise click.ClickException(
            f"MCP '{slug}' is not in the library manifest; add it first"
        )

    try:
        manifest = read_manifest(path)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if slug not in manifest:
        raise click.ClickException(
            f"MCP '{slug}' is not in the library manifest; run: "
            "agent-toolkit-cli mcp doctor -g"
        )

    entry = manifest[slug]
    old_version = entry.resolved_version
    updated_entry, note = _reresolve(entry, slug)
    if note:
        click.echo(note, err=True)

    # Expected state is authoritative before either materialisation file.
    try:
        write_manifest(path, {**manifest, slug: updated_entry})
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        materialize_entry(library, updated_entry, overwrite=True)
    except OSError as exc:
        raise click.ClickException(
            f"manifest committed but {slug} materialisation failed"
        ) from exc

    effective_version = updated_entry.resolved_version
    library_moved = effective_version != old_version

    # Reachable scopes: global always; project only when a project lock exists
    # in cwd (detect via the lock filename, matching scope_and_roots' probe).
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    cwd_project = project_root or Path.cwd()
    scopes: list[tuple[str, Path | None]] = [("global", None)]
    if (cwd_project / _LOCK_FILENAME).is_file():
        scopes.append(("project", cwd_project))

    any_projection = False
    for scope, project in scopes:
        lock_path = lock_path_for_scope(scope, home=home, project=project)
        lock = read_lock(lock_path)
        harnesses = [lock_entry.harness for lock_entry in lock.get(slug, [])]
        if not harnesses:
            continue
        # #399: heal legacy project rows into the standard shared-file row.
        if scope == "project":
            harnesses = list(
                normalize_harness_tokens(tuple(harnesses), scope="project")
            )
        any_projection = True
        try:
            mcp_install.apply(
                slug=slug,
                harnesses=harnesses,
                scope=scope,
                library_root=library,
                home=home,
                project=project,
                force=True,
            )
        except (UnsupportedMcpHarnessError, InstallError) as exc:
            raise click.ClickException(str(exc)) from exc
        if library_moved:
            click.echo(
                f"{slug}: {old_version or 'floating'} → "
                f"{effective_version or 'floating'} "
                f"({', '.join(sorted(harnesses))}) [{scope}]"
            )
        else:
            click.echo(
                f"{slug}: up to date ({effective_version or 'floating'}) "
                f"({', '.join(sorted(harnesses))}) [{scope}]"
            )

    if not any_projection:
        click.echo(
            f"{slug}: library now at {effective_version or 'floating'}; "
            "no locked projections to refresh"
        )
