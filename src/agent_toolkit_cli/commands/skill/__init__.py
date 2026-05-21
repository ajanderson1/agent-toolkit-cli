"""`agent-toolkit-cli skill ...` subcommand group."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_agents import AGENTS, detect_installed_agents
from agent_toolkit_cli.skill_install import (
    InstallError, InstallPlan, apply as engine_apply,
    install, uninstall,
)
from agent_toolkit_cli.skill_lock import read_lock, remove_entry, write_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir, lock_file_path,
)
from agent_toolkit_cli.skill_source import SourceParseError, parse_source

from ._common import scope_and_roots, validate_agent_names
from .list_cmd import list_cmd
from .push_cmd import push_cmd
from .status_cmd import status_cmd
from .update_cmd import update_cmd


@click.group()
def skill() -> None:
    """Manage skills via per-skill upstream git repos + skills-lock.json."""


@skill.command("add")
@click.argument("source", required=True)
@click.option("--slug", default=None,
              help="Override the local slug (defaults to repo name).")
@click.option("--ref", default=None, help="Branch or tag to install.")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--agent", multiple=True,
              help="Restrict to specific agent names (skills.sh catalog).")
@click.option("-y", "--yes", "yes", is_flag=True,
              help="Non-interactive; install to all detected agents.")
@click.pass_context
def add(
    ctx: click.Context, source: str, slug: str | None, ref: str | None,
    global_: bool, project_flag: bool, agent: tuple[str, ...], yes: bool,
) -> None:
    """Add a skill from SOURCE (owner/repo, URL, or local path)."""
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise click.UsageError(str(exc)) from exc
    if slug is None:
        if parsed.owner_repo:
            slug = parsed.owner_repo.split("/", 1)[1]
            # Strip trailing "-skill" to match skills.sh's convention
            # of repos named like "ajanderson1/journal-skill" -> "journal".
            if slug.endswith("-skill"):
                slug = slug[:-6]
        else:
            slug = Path(parsed.url).name
    if ref is not None:
        parsed = dataclasses.replace(parsed, ref=ref)

    if agent:
        agents = validate_agent_names(agent)
        scope, home, project_root = scope_and_roots(
            global_, project_flag,
            ctx.obj.get("project_root") if ctx.obj else None,
        )
    elif yes:
        agents = tuple(detect_installed_agents())
        scope, home, project_root = scope_and_roots(
            global_, project_flag,
            ctx.obj.get("project_root") if ctx.obj else None,
        )
    else:
        from . import wizard as _wizard
        canonical_preview = canonical_skill_dir(
            slug, scope="global", home=Path.home(), project=None,
        )
        choice = _wizard.select_agents_to_add(
            slug=slug, canonical_path=canonical_preview,
        )
        agents = choice.agents
        if choice.scope == "global":
            scope, home, project_root = "global", Path.home(), None
        else:
            scope, home, project_root = "project", None, Path.cwd()

    if not agents:
        click.echo(f"{slug}: no agents selected; nothing to do")
        return

    try:
        from agent_toolkit_cli.skill_install import plan
        p = plan(
            slug=slug, scope=scope, source=parsed, ref=parsed.ref,
            target_agents=agents, home=home, project=project_root,
        )
        engine_apply(p, home=home, project=project_root, env=None)
    except InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"added {slug} <- {parsed.url}")


@skill.command("remove")
@click.argument("slugs", nargs=-1, required=False)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--force", is_flag=True, help="Remove even if working tree is dirty.")
@click.pass_context
def remove_cmd(
    ctx: click.Context, slugs: tuple[str, ...], global_: bool,
    project_flag: bool, force: bool,
) -> None:
    """Remove a skill: canonical clone, projections, and lock entry."""
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)

    if not slugs:
        from . import wizard as _wizard
        installed = tuple(sorted(lock.skills))
        descriptions = {s: f"linked: {_count_linked(s, scope, home, project_root)}"
                        for s in installed}
        picked = _wizard.select_slug_to_remove(
            installed_slugs=installed, slug_descriptions=descriptions,
        )
        slugs = picked.slugs
        if not slugs:
            click.echo("(nothing selected)")
            return

    had_dirty = False
    for slug in slugs:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            continue
        effective_force = force
        if not force:
            from . import wizard as _wizard
            canonical = canonical_skill_dir(
                slug, scope=scope, home=home, project=project_root,
            )
            will_delete = [str(canonical)]
            for name in AGENTS:
                if not AGENTS[name].show_in_universal_list and name == "universal":
                    continue
                try:
                    from agent_toolkit_cli.skill_paths import agent_projection_dir
                    link = agent_projection_dir(
                        name, slug, scope=scope, home=home, project=project_root,
                    )
                    if link.is_symlink():
                        will_delete.append(str(link))
                except Exception:
                    pass
            mode = _wizard.select_remove_mode(
                slug=slug, will_delete=tuple(will_delete),
            )
            if not mode.confirmed:
                click.echo(f"{slug}: skipped")
                continue
            if mode.mode == "unlink":
                p = InstallPlan(
                    slug=slug, scope=scope, source=None, ref=None,
                    add_agents=(),
                    remove_agents=tuple(n for n in AGENTS
                                        if n != "universal"),
                )
                engine_apply(p, home=home, project=project_root, env=None)
                click.echo(f"{slug}: unlinked (canonical kept)")
                continue
            effective_force = True

        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )
        if canonical.exists() and skill_git.is_git_repo(canonical) and not effective_force:
            wt = skill_git.status(canonical, env=None)
            if wt == skill_git.GitWorkingTreeStatus.DIRTY:
                click.echo(f"{slug}: dirty — push or use --force to discard")
                had_dirty = True
                continue
        # Full remove: unlink all + rmtree canonical.
        from agent_toolkit_cli.skill_paths import SUPPORTED_HARNESSES
        uninstall(
            slug=slug, scope=scope, home=home, project=project_root,
            harnesses=SUPPORTED_HARNESSES,
        )
        lock = remove_entry(lock, slug)
        write_lock(lock_path, lock)
        click.echo(f"{slug}: removed")
    if had_dirty:
        ctx.exit(1)


def _count_linked(slug: str, scope: str, home: Path | None, project: Path | None) -> str:
    from agent_toolkit_cli.skill_install import _current_linked_agents
    linked = _current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
    )
    return ", ".join(linked[:3]) + ("..." if len(linked) > 3 else "")


skill.add_command(list_cmd)
skill.add_command(status_cmd)
skill.add_command(update_cmd)
skill.add_command(push_cmd)
