"""`agent-toolkit doctor` — environment / linkage / drift health-check."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit.doctor import (
    conventions as g_conventions,
    environment as g_environment,
    frontmatter as g_frontmatter,
    submodules as g_submodules,
    symlinks as g_symlinks,
)
from agent_toolkit.doctor.per_resource import diagnose
from agent_toolkit.doctor.result import GroupResult, Status

_GROUPS = ("environment", "symlink-integrity", "conventions", "submodule-health", "frontmatter")


@click.command()
@click.argument("slug", required=False)
@click.option("--repo-root", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--verbose", is_flag=True, help="Expand each group's evidence.")
@click.option("--group", "group_name", type=click.Choice(_GROUPS), default=None)
@click.option("--harness", type=click.Choice(["claude", "codex", "opencode", "pi"]), default="claude")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
@click.option("--exit-code", "use_exit_code", is_flag=True)
@click.option("--deep", is_flag=True, help="Reserved for future behavioural probes.")
def doctor(
    slug: str | None,
    repo_root: str,
    verbose: bool,
    group_name: str | None,
    harness: str,
    scope: str,
    use_exit_code: bool,
    deep: bool,
) -> None:
    root = Path(repo_root).resolve()
    if slug is not None:
        result = diagnose(root, slug=slug, deep=deep)
        _print_result(result, verbose=True)
        if use_exit_code and result.status == Status.FAIL:
            raise SystemExit(1)
        return

    results = _run_global(root, harness=harness, group_name=group_name)
    for r in results:
        _print_result(r, verbose=verbose)
    worst = max((r.status for r in results), default=Status.OK)
    if use_exit_code and worst == Status.FAIL:
        raise SystemExit(1)


def _run_global(root: Path, *, harness: str, group_name: str | None) -> list[GroupResult]:
    runners: list[tuple[str, callable]] = [
        ("environment", lambda: g_environment.run(root)),
        ("symlink-integrity", lambda: g_symlinks.run(root, harness=harness)),
        ("conventions", lambda: g_conventions.run(root, harness=harness)),
        ("submodule-health", lambda: g_submodules.run(root)),
        ("frontmatter", lambda: g_frontmatter.run(root)),
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
