"""`agent remove <slug>` — drop the store copy + global lock entry.

Dirty-guard: refuse if the store copy has uncommitted git changes unless
--force. All harness projections are removed first (via each adapter's
uninstall()), then the canonical library dir and lock entry are dropped.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import agent_install, skill_git
from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import (
    library_agent_path,
    library_lock_path,
)
from agent_toolkit_cli.skill_agents import AGENTS


def _all_enabled_harnesses() -> tuple[str, ...]:
    """Return all harness names whose subagent_mechanism != 'none'."""
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
    result = []
    for name, cfg in AGENTS.items():
        if cfg.subagent_mechanism == "none":
            continue
        try:
            get_adapter(name)
            result.append(name)
        except (UnsupportedMechanismError, Exception):
            pass
    return tuple(result)


@click.command("remove")
@click.argument("slug")
@click.option("--force", is_flag=True, help="Remove even if the store copy is dirty.")
def remove_cmd(slug: str, force: bool) -> None:
    """Remove an agent from the global library (projections + lock entry + canonical)."""
    lock_path = library_lock_path()
    lock = read_lock(lock_path)

    if slug not in lock.skills:
        raise click.ClickException(f"{slug}: not in the global library")

    canonical = library_agent_path(slug)
    if canonical.exists() and skill_git.is_git_repo(canonical):
        if (
            skill_git.status(canonical, env=None)
            == skill_git.GitWorkingTreeStatus.DIRTY
            and not force
        ):
            raise click.ClickException(
                f"{slug}: store copy has uncommitted changes; "
                f"push/commit them or re-run with --force"
            )

    # Full removal: harness projections + lock entry + canonical. `remove()` is
    # the destructive counterpart to `uninstall()` (issue #303): `uninstall`
    # detaches projections only and KEEPS the library, so `remove` must own the
    # canonical + lock deletion explicitly. (idempotent — adapters handle
    # missing files.)
    # Pass explicit home=Path.home() so adapters can resolve {HOME} templates
    # correctly (home=None causes ValueError in _expand for global templates).
    agent_install.remove(
        slug=slug, scope="global", home=Path.home(), project=None,
        harnesses=_all_enabled_harnesses(),
    )

    click.echo(f"removed {slug}")
