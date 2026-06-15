"""`mcp update <slug>` — greedy re-resolve + re-project. NO scope flag.

(1) Re-resolve the library entry's source (same per-method resolution as add).
    If the version moved, rewrite the library config.json args + sidecar
    resolved_version. `--url` sources have nothing to resolve; `--local`
    refreshes the recorded git HEAD SHA.
(2) Re-upsert every REACHABLE locked projection: every harness in the GLOBAL
    lock for the slug, plus every harness in the CURRENT PROJECT's lock when
    run inside a project. Upserts are idempotent; the pin is refreshed on each.

The library is the single version authority; the scope answers only WHERE the
slug is projected.
"""
from __future__ import annotations

import json
from pathlib import Path

import click
import yaml  # type: ignore[import-untyped]

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.commands.mcp import _resolve
from agent_toolkit_cli.commands.mcp._common import _LOCK_FILENAME, normalize_harness_tokens
from agent_toolkit_cli.mcp_adapters import UnsupportedMcpHarnessError
from agent_toolkit_cli.mcp_library import library_root, load_mcp_asset
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock


def _reresolve(asset, slug: str) -> tuple[str | None, str | None]:
    """Re-resolve the current version for a library asset's source.

    Returns (new_version, note). `new_version` is the freshly resolved string,
    or None when the method has nothing to resolve (url) or resolution failed
    (entry left unchanged). `note` is an optional stderr message (used for the
    --local honest-failure case). install_method drives the resolver, mirroring
    add_cmd.
    """
    method = asset.install_method
    inner = asset.inner_config
    if method == "npx":
        pkg = _npm_pkg_from_inner(inner)
        return (_resolve.resolve_npm_version(pkg) if pkg else None), None
    if method == "uvx":
        pkg = _uvx_pkg_from_inner(inner)
        return (_resolve.resolve_pypi_version(pkg) if pkg else None), None
    if method == "docker":
        # The tag IS the version authority; re-read it from args (unchanged).
        image = _docker_image_from_inner(inner)
        return (image.rsplit(":", 1)[-1] if image and ":" in image else None), None
    if method == "local":
        # The source dir is persisted in the sidecar by `mcp add --local`
        # (inner_config records only the command, not the dir). Entries authored
        # before that fix have no source_dir — report honestly, never crash, and
        # never print a false "up to date".
        source_dir = asset.metadata.get("source_dir")
        if not source_dir:
            return None, (
                f"note: {slug} is a --local entry with no recorded source_dir; "
                f"cannot refresh SHA (re-add to record it)"
            )
        directory = Path(source_dir)
        sha = _resolve.resolve_git_head_sha(directory)
        if sha is None:
            return None, (
                f"note: {slug} source_dir {source_dir} is missing or not a git "
                f"repo; cannot refresh SHA"
            )
        return sha, None
    # url, or unknown: nothing to resolve.
    return None, None


def _npm_pkg_from_inner(inner: dict) -> str | None:
    """`npx -y <pkg>[@ver]` → bare `<pkg>` (drop a trailing @version)."""
    args = inner.get("args", [])
    spec = args[-1] if args else None
    if not isinstance(spec, str):
        return None
    if spec.startswith("@"):  # scoped: @scope/name@ver
        scope_name, _, _ver = spec.rpartition("@")
        return scope_name if scope_name else spec
    return spec.split("@", 1)[0]


def _uvx_pkg_from_inner(inner: dict) -> str | None:
    """`uvx <pkg>[==ver]` → bare `<pkg>`."""
    args = inner.get("args", [])
    spec = args[-1] if args else None
    if not isinstance(spec, str):
        return None
    return spec.split("==", 1)[0]


def _docker_image_from_inner(inner: dict) -> str | None:
    """`docker run --rm -i <image:tag>` → `<image:tag>`."""
    args = inner.get("args", [])
    return args[-1] if args and isinstance(args[-1], str) else None


def _rewrite_library(library: Path, slug: str, asset, new_version: str) -> dict:
    """Rewrite config.json args (re-pin the version) + sidecar resolved_version.
    Returns the new inner config dict."""
    method = asset.install_method
    inner = dict(asset.inner_config)
    args = list(inner.get("args", []))
    if method == "npx" and args:
        pkg = _npm_pkg_from_inner(asset.inner_config)
        if pkg:
            args[-1] = f"{pkg}@{new_version}"
            inner["args"] = args
    elif method == "uvx" and args:
        pkg = _uvx_pkg_from_inner(asset.inner_config)
        if pkg:
            args[-1] = f"{pkg}=={new_version}"
            inner["args"] = args
    # docker/local: the tag/SHA is the version; args already carry it (docker)
    # or there's nothing to re-pin (local). Only the sidecar changes.

    (library / slug / "config.json").write_text(
        json.dumps(inner, indent=2) + "\n", encoding="utf-8"
    )
    metadata = dict(asset.metadata)
    metadata["resolved_version"] = new_version
    (library / f"{slug}.toolkit.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=True), encoding="utf-8"
    )
    return inner


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
    try:
        asset = load_mcp_asset(library, slug)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    old_version = asset.resolved_version
    new_version, note = _reresolve(asset, slug)
    if note:
        click.echo(note, err=True)

    if new_version is not None and new_version != old_version:
        _rewrite_library(library, slug, asset, new_version)
        # Reload so re-projection uses the rewritten inner config.
        asset = load_mcp_asset(library, slug)

    effective_version = asset.resolved_version
    # The LIBRARY is the version authority — "moved" is decided by whether its
    # resolved_version changed, NOT by sampling one harness's lock pin (which
    # misreports when harnesses in a scope hold divergent pins).
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
        harnesses = [e.harness for e in lock.get(slug, [])]
        if not harnesses:
            continue
        # #399: heal a LEGACY project lock — if its rows intersect the covered
        # set {claude-code, pi}, normalize them to `standard` so this update's
        # project apply() writes a standard row and collapse-on-install drops the
        # legacy rows (update is a converging path, not a re-blesser). Global is
        # left literal (claude-code/pi have separate global files).
        if scope == "project":
            harnesses = list(normalize_harness_tokens(tuple(harnesses), scope="project"))
        any_projection = True
        try:
            mcp_install.apply(
                slug=slug, harnesses=harnesses, scope=scope,
                library_root=library, home=home, project=project,
                force=True,  # update never re-prompts the running-claude guard
            )
        except (UnsupportedMcpHarnessError, InstallError) as exc:
            raise click.ClickException(str(exc)) from exc
        # Report per scope, keyed off the LIBRARY version change (authoritative
        # for every listed harness — apply() re-pins them all to it).
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
            f"no locked projections to refresh"
        )
