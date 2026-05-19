"""`agent-toolkit doctor` — environment / linkage / drift health-check."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli._support import ALL_HARNESSES
from agent_toolkit_cli._ui import header, summary
from agent_toolkit_cli.doctor import (
    allowlist_audit as g_allowlist_audit,
    conventions as g_conventions,
    duplicates as g_duplicates,
    environment as g_environment,
    frontmatter as g_frontmatter,
    harness_homes as g_harness_homes,
    orphans as g_orphans,
    submodules as g_submodules,
    symlinks as g_symlinks,
    user_scope_coverage as g_user_scope_coverage,
)
from agent_toolkit_cli.doctor.per_resource import diagnose
from agent_toolkit_cli.doctor.result import GroupResult, Status

_GROUPS = (
    "environment", "symlink-integrity", "conventions", "submodule-health",
    "frontmatter", "duplicates", "harness-homes", "allowlist-audit", "mcps",
    "user-scope-coverage", "orphans",
)


@click.command(short_help="Run five-group health check (or per-resource diagnosis).")
@click.argument("slug", required=False)
@click.option(
    "--toolkit-repo",
    "toolkit_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the agent-toolkit repo (defaults to group --toolkit-repo / env / walk-up / ~/GitHub/agent-toolkit).",
)
@click.option("--verbose", is_flag=True, help="Expand each group's evidence.")
@click.option("--group", "group_name", type=click.Choice(_GROUPS), default=None)
@click.option("--harness", type=click.Choice(list(ALL_HARNESSES)), default="claude")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
@click.option("--exit-code", "use_exit_code", is_flag=True)
@click.option("--deep", is_flag=True, help="Reserved for future behavioural probes.")
@click.pass_context
def doctor(
    ctx: click.Context,
    slug: str | None,
    toolkit_root: Path | None,
    verbose: bool,
    group_name: str | None,
    harness: str,
    scope: str,
    use_exit_code: bool,
    deep: bool,
) -> None:
    """Five-group health check for the toolkit. Pass a slug for per-resource diagnosis."""
    if toolkit_root is None:
        toolkit_root = (ctx.obj or {}).get("toolkit_root")
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(explicit=None)
        except RepoNotFoundError as exc:
            raise click.ClickException(str(exc))
    else:
        toolkit_root = Path(toolkit_root).resolve()
    root = toolkit_root
    if slug is not None:
        header(f"Diagnosing {slug}...")
        result = diagnose(root, slug=slug, deep=deep)
        _print_result(result, verbose=True)
        summary(f"{result.status.label()}: {result.summary}")
        if use_exit_code and result.status == Status.FAIL:
            raise SystemExit(1)
        return

    header(f"Running doctor groups (harness={harness})...")
    results = _run_global(root, harness=harness, scope=scope, group_name=group_name)
    for r in results:
        _print_result(r, verbose=verbose)
    worst = max((r.status for r in results), default=Status.OK)
    counts = {Status.ADVISORY: 0, Status.OK: 0, Status.WARN: 0, Status.FAIL: 0}
    for r in results:
        counts[r.status] += 1
    summary(
        f"{counts[Status.OK]} OK, {counts[Status.WARN]} WARN, {counts[Status.FAIL]} FAIL, "
        f"{counts[Status.ADVISORY]} INFO. "
        f"Worst: {worst.label()}."
    )
    if use_exit_code and worst == Status.FAIL:
        raise SystemExit(1)


def _run_global(
    root: Path, *, harness: str, scope: str, group_name: str | None
) -> list[GroupResult]:
    from agent_toolkit_cli.doctor import mcps as g_mcps  # noqa: PLC0415
    runners: list[tuple[str, callable]] = [
        ("environment", lambda: g_environment.run(root)),
        ("symlink-integrity", lambda: g_symlinks.run(root, harness=harness)),
        ("conventions", lambda: g_conventions.run(root, harness=harness)),
        ("submodule-health", lambda: g_submodules.run(root)),
        ("frontmatter", lambda: g_frontmatter.run(root)),
        ("duplicates", lambda: g_duplicates.run(root)),
        ("harness-homes", lambda: g_harness_homes.run()),
        ("allowlist-audit", lambda: g_allowlist_audit.run(root, project_root=Path.cwd())),
        ("mcps", lambda: g_mcps.run(root, harness=harness, scope=scope, project_root=Path.cwd())),
        ("user-scope-coverage", lambda: g_user_scope_coverage.run(root, project_root=Path.cwd())),
        ("orphans", lambda: g_orphans.run(root)),
    ]
    if group_name:
        runners = [(n, fn) for (n, fn) in runners if n == group_name]
    return [fn() for (_n, fn) in runners]


def _print_result(r: GroupResult, *, verbose: bool) -> None:
    label = r.status.label()
    click.echo(f"[{label:<4}] {r.name:<18} {r.summary}")
    if verbose or r.status != Status.OK:
        for f in r.findings:
            click.echo(f"          {f}")
        if r.fix_hint:
            click.echo(f"   fix:   {r.fix_hint}")
