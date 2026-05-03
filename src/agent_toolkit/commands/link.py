# src/agent_toolkit/commands/link.py
"""link — project allow-listed assets as symlinks per (scope, harness)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import click

from agent_toolkit import _ui
from agent_toolkit._allowlist import SECTIONS, kind_to_section, read_allowlist
from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit.commands._link_lib import (
    KINDS_FOR_PROJECTION,
    LinkCounters,
    MALFORMED,
    _asset_harnesses,
    format_summary,
    harness_target_dir,
    iter_plan_lines,
    project_from_file,
)
from agent_toolkit.commands._yaml_edit import add_slug, write_snapshot
from agent_toolkit.walker import discover_assets


@click.command("link")
@click.argument("scope", type=click.Choice(["user", "project"]))
@click.argument("harness")  # accept any string; conventions/etc dispatched by sibling cmd
@click.argument("target", required=False, default=None)
@click.option("--all", "all_flag", is_flag=True, default=False)
@click.option(
    "--plan",
    "plan_flag",
    default=None,
    help="Read kind:slug entries from FILE (only '-' for stdin is supported).",
)
@click.option("-y", "--yes", "assume_yes", is_flag=True, default=False)
@click.option("--dry-run", "dry_run", is_flag=True, default=False)
@click.option("--quiet", "-q", is_flag=True, default=False)
@click.option(
    "--toolkit-repo",
    "toolkit_repo",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--project",
    "project_flag",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.pass_context
def link(
    ctx,
    scope,
    harness,
    target,
    all_flag,
    plan_flag,
    assume_yes,
    dry_run,
    quiet,
    toolkit_repo,
    project_flag,
) -> None:
    """Project assets per the allow-list. Bare form reads the file."""
    if quiet:
        os.environ["AGENT_TOOLKIT_QUIET"] = "1"

    # Mode resolution + mutex checks
    if plan_flag is not None and plan_flag != "-":
        click.echo("--plan currently supports only '-' (stdin)", err=True)
        ctx.exit(2)
        return
    modes_set = sum(bool(x) for x in (all_flag, plan_flag is not None, target is not None))
    if modes_set > 1:
        if plan_flag is not None and all_flag:
            click.echo("cannot combine --all with plan mode", err=True)
        elif plan_flag is not None and target is not None:
            click.echo("cannot combine plan with per-asset mode", err=True)
        elif all_flag and target is not None:
            click.echo("cannot combine --all with per-asset mode", err=True)
        ctx.exit(2)
        return

    # Resolve toolkit_root via group context, flag, or four-step
    toolkit_root: Path | None = (ctx.obj or {}).get("toolkit_root") if ctx.obj else None
    if toolkit_repo is not None:
        try:
            toolkit_root = resolve_toolkit_root(toolkit_repo)
        except RepoNotFoundError as exc:
            click.echo(str(exc), err=True)
            ctx.exit(2)
            return
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(None)
        except RepoNotFoundError as exc:
            click.echo(str(exc), err=True)
            ctx.exit(2)
            return

    project_root = Path(project_flag).resolve() if project_flag else Path.cwd()
    allowlist_path = (
        Path(os.environ.get("HOME", "")) / ".agent-toolkit.yaml"
        if scope == "user"
        else project_root / ".agent-toolkit.yaml"
    )

    counters = LinkCounters()

    if all_flag:
        _do_all(
            scope, harness, toolkit_root, project_root,
            allowlist_path, assume_yes, dry_run, counters, ctx,
        )
        return
    if plan_flag is not None:
        _do_plan(
            scope, harness, toolkit_root, project_root,
            allowlist_path, dry_run, counters, ctx,
        )
        return
    if target is not None:
        _do_per_asset(
            scope, harness, target, toolkit_root, project_root,
            allowlist_path, dry_run, counters, ctx,
        )
        return
    _do_bare(scope, harness, toolkit_root, project_root, allowlist_path, dry_run, counters, ctx)


def _do_bare(scope, harness, toolkit_root, project_root, allowlist_path, dry_run, counters, ctx):
    if not allowlist_path.is_file():
        msg = (
            f"no {allowlist_path} found.\n"
            f"  agent-toolkit link {scope} {harness} --all"
            f"                  → snapshot every compatible asset, then project\n"
            f"  agent-toolkit link {scope} {harness} <kind>:<slug>"
            f"          → add one asset, then project\n"
            f"  $EDITOR {allowlist_path}"
            f"                                  → author by hand, then re-run\n"
        )
        click.echo(msg, err=True)
        ctx.exit(2)
        return
    if dry_run:
        _ui.header(
            f"Previewing {scope}-scope changes for {harness} (no files will be modified)..."
        )
    else:
        _ui.header(f"Linking {scope}-scope assets for {harness} from {allowlist_path}...")
    project_from_file(
        scope=scope,
        harness=harness,
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist_path,
        dry_run=dry_run,
        counters=counters,
        stdout=sys.stdout,
    )
    _ui.summary(format_summary(counters, dry_run))


def _do_per_asset(
    scope, harness, target, toolkit_root, project_root, allowlist_path, dry_run, counters, ctx
):
    # Parse kind:slug from target string
    if ":" not in target:
        click.echo(f"invalid target {target!r} — expected kind:slug", err=True)
        ctx.exit(2)
        return
    kind, _, slug = target.partition(":")

    # 1. mcp guard
    if kind == "mcp":
        click.echo(
            "mcps are not yet scope-routed — edit the harness's mcp.json directly",
            err=True,
        )
        ctx.exit(2)
        return

    # 2. resolve asset — find in toolkit
    found_asset_path: Path | None = None
    for asset in discover_assets(toolkit_root):
        if asset.kind == kind and asset.slug == slug:
            found_asset_path = asset.path
            break
    if found_asset_path is None:
        click.echo(
            f"no {kind} named '{slug}' found."
            f" Run 'agent-toolkit list {kind}' to see what's available.",
            err=True,
        )
        ctx.exit(1)
        return

    # 3. harness compatibility
    declared = _asset_harnesses(found_asset_path)
    if harness not in declared:
        csv = ", ".join(declared) if declared else "none"
        click.echo(
            f"{kind}:{slug} doesn't support harness '{harness}'"
            f" (declares: {csv}). Use a different harness or pick another asset.",
            err=True,
        )
        ctx.exit(1)
        return

    # 4. Mutate the YAML (idempotent add).
    # Real run: write to allowlist_path. Dry-run: write to a temp copy.
    try:
        section = kind_to_section(kind)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(2)
        return

    tmp_path: str | None = None
    target_path = allowlist_path
    if dry_run:
        fd, tmp_path = tempfile.mkstemp(prefix="agent-toolkit-add.")
        os.close(fd)
        if allowlist_path.is_file():
            Path(tmp_path).write_bytes(allowlist_path.read_bytes())
        target_path = Path(tmp_path)

    try:
        add_slug(target_path, section, slug)
    except (ValueError, OSError) as exc:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
        click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    # 5. project
    if dry_run:
        _ui.header(
            f"Previewing {scope}-scope changes for {harness} (no files will be modified)..."
        )
    else:
        _ui.header(f"Linking {scope}-scope {kind}:{slug} for {harness}...")
    project_from_file(
        scope=scope,
        harness=harness,
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=target_path,
        dry_run=dry_run,
        counters=counters,
        stdout=sys.stdout,
    )
    if tmp_path:
        Path(tmp_path).unlink(missing_ok=True)
    _ui.summary(format_summary(counters, dry_run))


def _link_file_has_slugs(allowlist_path: Path) -> bool:
    """Return True if any section in the allowlist has at least one slug."""
    if not allowlist_path.is_file():
        return False
    data = read_allowlist(allowlist_path)
    return any(bool(data.get(s)) for s in SECTIONS)


def _link_file_section_summary(allowlist_path: Path) -> str:
    """Return e.g. '2 skills, 0 agents, 0 commands, 0 hooks, 0 plugins'."""
    data = read_allowlist(allowlist_path)
    parts = []
    for section in SECTIONS:
        n = len(data.get(section, []))
        parts.append(f"{n} {section}")
    return ", ".join(parts)


def _do_all(
    scope, harness, toolkit_root, project_root,
    allowlist_path, assume_yes, dry_run, counters, ctx,
):
    # Confirm overwrite if file is populated
    if _link_file_has_slugs(allowlist_path):
        if not assume_yes:
            # Check if we have a TTY (CliRunner with input="" appears as non-TTY)
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                click.echo(
                    f"no TTY available — pass --yes/-y to confirm overwrite"
                    f" of existing {allowlist_path}.",
                    err=True,
                )
                ctx.exit(2)
                return
            counts = _link_file_section_summary(allowlist_path)
            click.echo(
                f"{allowlist_path} already has {counts}.\n"
                f"--all will replace this with every compatible asset for {harness}.",
                err=True,
            )
            reply = click.prompt("Continue? [y/N] ", default="N", err=True)
            if reply.strip().lower() not in ("y", "yes"):
                click.echo("aborted.", err=True)
                ctx.exit(2)
                return

    # Build the snapshot of all harness-compatible assets — single pass,
    # bucketed by kind (mirrors _link_lib.project_from_file).
    by_kind: dict[str, list] = {k: [] for k in KINDS_FOR_PROJECTION}
    for asset in discover_assets(toolkit_root):
        if asset.kind in by_kind:
            by_kind[asset.kind].append(asset)

    entries: list[tuple[str, str]] = []
    for kind in KINDS_FOR_PROJECTION:
        try:
            section = kind_to_section(kind)
        except ValueError:
            continue
        for asset in by_kind[kind]:
            if harness in _asset_harnesses(asset.path):
                entries.append((section, asset.slug))

    # Real run: write to allowlist_path. Dry-run: write to temp file.
    tmp_path: str | None = None
    target_path = allowlist_path
    if dry_run:
        fd, tmp_path = tempfile.mkstemp(prefix="agent-toolkit-snapshot.")
        os.close(fd)
        target_path = Path(tmp_path)

    try:
        write_snapshot(target_path, entries)
    except (ValueError, OSError) as exc:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
        click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    if dry_run:
        _ui.header(
            f"Previewing {scope}-scope --all snapshot for {harness}"
            f" (no files will be modified)..."
        )
    else:
        _ui.header(
            f"Snapshotted every {harness}-compatible asset into {allowlist_path}; projecting..."
        )

    project_from_file(
        scope=scope,
        harness=harness,
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=target_path,
        dry_run=dry_run,
        counters=counters,
        stdout=sys.stdout,
    )
    if tmp_path:
        Path(tmp_path).unlink(missing_ok=True)
    _ui.summary(format_summary(counters, dry_run))


def _do_plan(
    scope, harness, toolkit_root, project_root,
    allowlist_path, dry_run, counters, ctx,
):
    # Read all of stdin
    plan_text = click.get_text_stream("stdin").read()

    ok = 0
    failed = 0
    total = 0
    error_lines: list[str] = []

    for kind, slug in iter_plan_lines(plan_text):
        if kind == MALFORMED:
            error_lines.append(f"malformed (no kind:slug): {slug}")
            failed += 1
            total += 1
            continue
        total += 1
        # Run per-asset logic inline with quiet=True to suppress chrome
        old_quiet = os.environ.get("AGENT_TOOLKIT_QUIET")
        os.environ["AGENT_TOOLKIT_QUIET"] = "1"
        try:
            success = _do_plan_entry(
                scope, harness, kind, slug, toolkit_root, project_root,
                allowlist_path, dry_run, counters, error_lines,
            )
        finally:
            if old_quiet is None:
                os.environ.pop("AGENT_TOOLKIT_QUIET", None)
            else:
                os.environ["AGENT_TOOLKIT_QUIET"] = old_quiet
        if success:
            ok += 1
        else:
            failed += 1

    for line in error_lines:
        click.echo(line, err=True)

    _ui.summary(f"Plan applied: {ok} ok, {failed} failed (of {total} entries).")
    if failed > 0:
        ctx.exit(1)


def _do_plan_entry(
    scope, harness, kind, slug, toolkit_root, project_root,
    allowlist_path, dry_run, counters, error_lines,
) -> bool:
    """Execute one plan entry. Returns True on success, False on failure."""
    # mcp guard
    if kind == "mcp":
        error_lines.append(
            "mcps are not yet scope-routed — edit the harness's mcp.json directly"
        )
        return False

    # Find the asset
    found_asset_path: Path | None = None
    for asset in discover_assets(toolkit_root):
        if asset.kind == kind and asset.slug == slug:
            found_asset_path = asset.path
            break
    if found_asset_path is None:
        error_lines.append(
            f"no {kind} named '{slug}' found."
            f" Run 'agent-toolkit list {kind}' to see what's available."
        )
        return False

    # Harness compatibility
    declared = _asset_harnesses(found_asset_path)
    if harness not in declared:
        csv = ", ".join(declared) if declared else "none"
        error_lines.append(
            f"{kind}:{slug} doesn't support harness '{harness}'"
            f" (declares: {csv}). Use a different harness or pick another asset."
        )
        return False

    # Get section
    try:
        section = kind_to_section(kind)
    except ValueError as exc:
        error_lines.append(str(exc))
        return False

    # Mutate YAML
    tmp_path: str | None = None
    target_path = allowlist_path
    if dry_run:
        fd, tmp_path = tempfile.mkstemp(prefix="agent-toolkit-plan.")
        os.close(fd)
        if allowlist_path.is_file():
            Path(tmp_path).write_bytes(allowlist_path.read_bytes())
        target_path = Path(tmp_path)

    try:
        add_slug(target_path, section, slug)
        project_from_file(
            scope=scope,
            harness=harness,
            toolkit_root=toolkit_root,
            project_root=project_root,
            allowlist_path=target_path,
            dry_run=dry_run,
            counters=counters,
            stdout=sys.stdout,
        )
    except (ValueError, OSError) as exc:
        error_lines.append(f"failed: {kind}:{slug} — {exc}")
        return False
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    return True
