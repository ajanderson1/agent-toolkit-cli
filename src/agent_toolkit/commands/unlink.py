# src/agent_toolkit/commands/unlink.py
"""unlink — remove projected symlinks per (scope, harness)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from agent_toolkit import _ui
from agent_toolkit._allowlist import kind_to_section, read_allowlist
from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit.commands._link_lib import (
    KINDS_FOR_PROJECTION,
    MALFORMED,
    LinkCounters,
    format_summary,
    harness_target_dir,
    iter_plan_lines,
    project_from_file,
)
from agent_toolkit.commands._yaml_edit import remove_slug


@click.command("unlink")
@click.argument("scope", type=click.Choice(["user", "project"]))
@click.argument("harness")
@click.argument("target", required=False, default=None)
@click.option("--all", "all_flag", is_flag=True, default=False)
@click.option(
    "--plan",
    "plan_flag",
    default=None,
    help="Read kind:slug entries from FILE (only '-' for stdin is supported).",
)
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
def unlink(
    ctx,
    scope,
    harness,
    target,
    all_flag,
    plan_flag,
    dry_run,
    quiet,
    toolkit_repo,
    project_flag,
) -> None:
    """Remove projected symlinks per the allow-list."""
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

    if all_flag:
        _do_all(scope, harness, toolkit_root, project_root, dry_run)
        return
    if plan_flag is not None:
        _do_plan(scope, harness, toolkit_root, project_root, allowlist_path, dry_run, ctx)
        return
    if target is not None:
        _do_per_asset(
            scope, harness, target, toolkit_root, project_root, allowlist_path, dry_run, ctx
        )
        return
    _do_bare(scope, harness, allowlist_path, ctx)


def _do_bare(scope, harness, allowlist_path, ctx):
    msg = (
        f"unlink requires a target. Did you mean:\n"
        f"  agent-toolkit unlink {scope} {harness} --all"
        f"                  → remove all symlinks for {harness}"
        f" (preserves {allowlist_path})\n"
        f"  agent-toolkit unlink {scope} {harness} <kind>:<slug>"
        f"          → remove one asset (also removes from {allowlist_path})\n"
        f"Run 'agent-toolkit list {harness}' to see what's currently linked."
    )
    click.echo(msg, err=True)
    ctx.exit(2)


def _do_all(scope, harness, toolkit_root, project_root, dry_run):
    if dry_run:
        _ui.header(
            f"Previewing removal of {scope}-scope {harness} symlinks"
            f" pointing into {toolkit_root}..."
        )
    else:
        _ui.header(
            f"Removing {scope}-scope {harness} symlinks"
            f" pointing into {toolkit_root}..."
        )

    removed = 0
    for kind in KINDS_FOR_PROJECTION:
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None or not target_dir.is_dir():
            continue
        for entry in target_dir.iterdir():
            if not entry.is_symlink():
                continue
            raw_target = os.readlink(entry)
            # Mirrors bash `case "$target" in "$toolkit_root"/*)` — raw string
            # prefix match. Intentionally diverges from
            # _link_lib._prune_if_into_repo, which resolves symlinks; this path
            # is byte-faithful to the bash version.
            toolkit_prefix = str(toolkit_root)
            if raw_target == toolkit_prefix or raw_target.startswith(toolkit_prefix + "/"):
                if dry_run:
                    print(f"would-unlink: {entry}", file=sys.stdout)
                else:
                    entry.unlink()
                removed += 1

    if dry_run:
        _ui.summary(f"{removed} symlinks would be removed.")
    else:
        _ui.summary(f"Removed {removed} symlinks.")


def _do_per_asset(
    scope, harness, target, toolkit_root, project_root, allowlist_path, dry_run, ctx
):
    if ":" not in target:
        click.echo(f"invalid target {target!r} — expected kind:slug", err=True)
        ctx.exit(2)
        return
    kind, _, slug = target.partition(":")

    if kind == "mcp":
        click.echo(
            "mcps are not yet scope-routed — edit the harness's mcp.json directly",
            err=True,
        )
        ctx.exit(2)
        return

    try:
        section = kind_to_section(kind)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(2)
        return

    if not allowlist_path.is_file():
        click.echo(f"no {allowlist_path} — nothing to unlink.", err=True)
        ctx.exit(1)
        return

    # Idempotent diagnostic: if slug is absent, say so and exit 0
    allowed = read_allowlist(allowlist_path)
    slugs_in_section = list(allowed.get(section, []))
    if slug not in slugs_in_section:
        click.echo(
            f"{kind}:{slug} not in {allowlist_path} — nothing to remove.", err=True
        )
        return  # exit 0

    # Remove from YAML (real run only)
    if not dry_run:
        try:
            remove_slug(allowlist_path, section, slug)
        except (ValueError, OSError) as exc:
            click.echo(str(exc), err=True)
            ctx.exit(1)
            return

    _ui.header(f"Unlinking {scope}-scope {kind}:{slug} for {harness}...")

    # Re-project to prune the symlink
    counters = LinkCounters()
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


def _do_plan(scope, harness, toolkit_root, project_root, allowlist_path, dry_run, ctx):
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
        old_quiet = os.environ.get("AGENT_TOOLKIT_QUIET")
        os.environ["AGENT_TOOLKIT_QUIET"] = "1"
        try:
            success = _do_plan_entry(
                scope, harness, kind, slug, toolkit_root, project_root,
                allowlist_path, dry_run, error_lines,
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
    allowlist_path, dry_run, error_lines,
) -> bool:
    """Execute one plan entry for unlink. Returns True on success, False on failure."""
    if kind == "mcp":
        error_lines.append(
            "mcps are not yet scope-routed — edit the harness's mcp.json directly"
        )
        return False

    try:
        section = kind_to_section(kind)
    except ValueError as exc:
        error_lines.append(str(exc))
        return False

    if not allowlist_path.is_file():
        error_lines.append(f"no {allowlist_path} — nothing to unlink.")
        return False

    allowed = read_allowlist(allowlist_path)
    slugs_in_section = list(allowed.get(section, []))
    if slug not in slugs_in_section:
        # Idempotent — not an error in plan mode
        return True

    if not dry_run:
        try:
            remove_slug(allowlist_path, section, slug)
        except (ValueError, OSError) as exc:
            error_lines.append(f"failed: {kind}:{slug} — {exc}")
            return False

    counters = LinkCounters()
    try:
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
    except (ValueError, OSError) as exc:
        error_lines.append(f"failed: {kind}:{slug} — {exc}")
        return False

    return True
