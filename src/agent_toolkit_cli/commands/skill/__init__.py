"""`agent-toolkit-cli skill ...` subcommand group."""
from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_agents import AGENTS, detect_installed_agents
from agent_toolkit_cli.skill_install import (
    DirtyCanonicalError,
    InstallError,
    InstallPlan,
    _current_linked_agents,
    _universal_bundle_link,
    apply as engine_apply,
    plan as engine_plan,
    uninstall,
)
from agent_toolkit_cli.skill_lock import read_lock, remove_entry, write_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    library_lock_path,
    library_skill_path,
    lock_file_path,
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


def _resolve_agents(agents_str: str, scope: str) -> tuple[str, ...]:
    """Expand a comma-separated --agents string into a tuple of agent names.

    Special values:
      "universal" → the universal bundle token (creates ~/.agents/skills/<slug>)
      "all"       → every agent detected as installed at the given scope
    """
    if agents_str == "all":
        return tuple(detect_installed_agents())
    parts = [p.strip() for p in agents_str.split(",") if p.strip()]
    # "universal" is a valid token; other names must be in the catalog.
    unknown = [p for p in parts if p != "universal" and p not in AGENTS]
    if unknown:
        raise click.UsageError(f"unknown agent(s): {', '.join(unknown)}")
    return tuple(parts)


@skill.command("add")
@click.argument("source", required=True)
@click.option("--slug", default=None,
              help="Override the local slug (defaults to repo name).")
@click.option("--ref", default=None, help="Branch or tag to clone.")
@click.pass_context
def add(
    ctx: click.Context, source: str, slug: str | None, ref: str | None,
) -> None:
    """Clone SOURCE into the library. No symlinks created.

    Use `skill install <slug> --agents ...` to make the skill visible to agents.
    """
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise click.UsageError(str(exc)) from exc

    if slug is None:
        if parsed.owner_repo:
            slug = parsed.owner_repo.split("/", 1)[1]
            if slug.endswith("-skill"):
                slug = slug[:-6]
        else:
            slug = Path(parsed.url).name

    if ref is not None:
        parsed = dataclasses.replace(parsed, ref=ref)

    library_dir = library_skill_path(slug)
    lock_path = library_lock_path()

    from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock
    lock = read_lock(lock_path)
    existing_entry = lock.skills.get(slug)

    if existing_entry is not None:
        requested = parsed.owner_repo or parsed.url
        if existing_entry.source != requested:
            raise click.ClickException(
                f"{slug}: library entry exists with source {existing_entry.source!r}; "
                f"refusing to overwrite with {requested!r}. "
                f"Run `skill remove {slug}` first."
            )

    if not library_dir.exists():
        library_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone(parsed.url, library_dir, ref=parsed.ref, env=None)
        except Exception as exc:
            raise click.ClickException(f"clone failed: {exc}") from exc

    if skill_git.is_git_repo(library_dir):
        upstream_sha = skill_git.remote_head_sha(
            library_dir, ref=parsed.ref or "main", env=None,
        )
        local_sha = skill_git.head_sha(library_dir, env=None)
    else:
        upstream_sha = None
        local_sha = None

    entry = LockEntry(
        source=parsed.owner_repo or parsed.url,
        source_type=parsed.type,
        ref=parsed.ref,
        skill_path="SKILL.md",
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))
    click.echo(f"added {slug} to library <- {parsed.url}")


@skill.command("install")
@click.argument("slug", required=True)
@click.option("--agents", "agents_str", required=True,
              help="Comma-separated agent names, 'universal', or 'all'.")
@click.option("--scope", "scope", default="global",
              type=click.Choice(["global", "project"]),
              help="Scope: global (default) or project.")
@click.option("-p", "--project", "project_flag", is_flag=True,
              help="Shorthand for --scope project.")
@click.pass_context
def install_cmd(
    ctx: click.Context, slug: str, agents_str: str,
    scope: str, project_flag: bool,
) -> None:
    """Create agent-visibility symlinks for a library skill.

    The skill must already be in the library (run `skill add` first).
    For --scope project, the project canonical is cloned from the global
    library's recorded source if not already present.
    """
    if project_flag:
        scope = "project"

    try:
        target_agents = _resolve_agents(agents_str, scope)
    except click.UsageError:
        raise

    if not target_agents:
        click.echo(f"{slug}: no agents specified; nothing to do")
        return

    # Look up the global lock entry for the source/ref.
    global_lock_path = library_lock_path()
    global_lock = read_lock(global_lock_path)
    global_entry = global_lock.skills.get(slug)

    if scope == "global":
        # Library canonical must already exist.
        library_dir = library_skill_path(slug)
        if not library_dir.exists():
            raise click.ClickException(
                f"{slug}: not in library. Run `skill add <source>` first."
            )
        # Build the plan using the library canonical as the source of truth.
        # We don't clone again — just create symlinks.
        p = InstallPlan(
            slug=slug, scope="global",
            source=None, ref=None,
            add_agents=target_agents, remove_agents=(),
        )
        try:
            result = engine_apply(p, home=None, project=None, env=None)
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        created = result.created
        skipped = result.skipped

    else:
        # Project scope: canonical is at <project>/.agents/skills/<slug>/.
        project_root = (
            ctx.obj.get("project_root") if ctx.obj else None
        ) or Path.cwd()
        project_canonical = project_root / ".agents" / "skills" / slug

        # Clone from global lock source if not present.
        if not project_canonical.exists():
            if global_entry is None:
                raise click.ClickException(
                    f"{slug}: not in global library. "
                    f"Run `skill add <source>` first."
                )
            project_canonical.parent.mkdir(parents=True, exist_ok=True)
            source_url = (
                global_entry.extras.get("sourceUrl") or global_entry.source
            )
            try:
                skill_git.clone(
                    str(source_url), project_canonical,
                    ref=global_entry.ref, env=None,
                )
            except Exception as exc:
                raise click.ClickException(
                    f"clone for project scope failed: {exc}"
                ) from exc

        # Filter out "universal" for project scope — canonical IS the install.
        # Non-universal agents get symlinks per skip rules.
        non_universal = tuple(a for a in target_agents if a != "universal")
        p = InstallPlan(
            slug=slug, scope="project",
            source=None, ref=None,
            add_agents=non_universal, remove_agents=(),
        )
        try:
            result = engine_apply(p, home=None, project=project_root, env=None)
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        created = result.created
        skipped = result.skipped

        # Update project lock.
        from agent_toolkit_cli.skill_lock import LockEntry, add_entry
        project_lock_path = lock_file_path(
            scope="project", project=project_root,
        )
        project_lock = read_lock(project_lock_path)
        if slug not in project_lock.skills and global_entry is not None:
            proj_entry = LockEntry(
                source=global_entry.source,
                source_type=global_entry.source_type,
                ref=global_entry.ref,
                skill_path=global_entry.skill_path,
                upstream_sha=None,
                local_sha=None,
            )
            write_lock(project_lock_path, add_entry(project_lock, slug, proj_entry))

    if created:
        for link in created:
            click.echo(f"  linked {link}")
    if skipped:
        click.echo(f"  skipped (skip rule): {', '.join(skipped)}")
    click.echo(f"installed {slug} for {agents_str}")


@skill.command("uninstall")
@click.argument("slug", required=True)
@click.option("--agents", "agents_str", required=True,
              help="Comma-separated agent names, 'universal', or 'all'.")
@click.option("--scope", "scope", default="global",
              type=click.Choice(["global", "project"]),
              help="Scope: global (default) or project.")
@click.option("-p", "--project", "project_flag", is_flag=True,
              help="Shorthand for --scope project.")
@click.pass_context
def uninstall_cmd(
    ctx: click.Context, slug: str, agents_str: str,
    scope: str, project_flag: bool,
) -> None:
    """Remove agent-visibility symlinks. Library/project canonical untouched."""
    if project_flag:
        scope = "project"

    try:
        target_agents = _resolve_agents(agents_str, scope)
    except click.UsageError:
        raise

    if not target_agents:
        click.echo(f"{slug}: no agents specified; nothing to do")
        return

    if scope == "global":
        p = InstallPlan(
            slug=slug, scope="global",
            source=None, ref=None,
            add_agents=(), remove_agents=target_agents,
        )
        try:
            result = engine_apply(p, home=None, project=None, env=None)
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        removed = result.removed
    else:
        project_root = (
            ctx.obj.get("project_root") if ctx.obj else None
        ) or Path.cwd()
        non_universal = tuple(a for a in target_agents if a != "universal")
        p = InstallPlan(
            slug=slug, scope="project",
            source=None, ref=None,
            add_agents=(), remove_agents=non_universal,
        )
        try:
            result = engine_apply(p, home=None, project=project_root, env=None)
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        removed = result.removed

    if removed:
        for link in removed:
            click.echo(f"  unlinked {link}")
    click.echo(f"uninstalled {slug} for {agents_str}")


@skill.command("remove")
@click.argument("slugs", nargs=-1, required=False)
@click.option("--force", is_flag=True, help="Remove even if working tree is dirty.")
@click.pass_context
def remove_cmd(
    ctx: click.Context, slugs: tuple[str, ...], force: bool,
) -> None:
    """Remove a skill from the library (all symlinks + lock entry + library dir)."""
    lock_path = library_lock_path()
    lock = read_lock(lock_path)

    if not slugs:
        from . import wizard as _wizard
        installed = tuple(sorted(lock.skills))
        descriptions = {s: f"in library: {library_skill_path(s)}"
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
            click.echo(f"{slug}: not in library")
            continue

        library_dir = library_skill_path(slug)
        effective_force = force

        if not force:
            from . import wizard as _wizard
            will_delete = [str(library_dir)]
            # Enumerate known symlinks.
            bundle_link = _universal_bundle_link(slug)
            if bundle_link.is_symlink():
                will_delete.append(str(bundle_link))
            for name in AGENTS:
                if name == "universal":
                    continue
                try:
                    from agent_toolkit_cli.skill_paths import agent_projection_dir
                    link = agent_projection_dir(
                        name, slug, scope="global", home=None, project=None,
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
                # Remove all global symlinks but keep library dir + lock entry.
                _remove_all_global_symlinks(slug)
                click.echo(f"{slug}: unlinked (library kept)")
                continue
            effective_force = True

        if library_dir.exists() and skill_git.is_git_repo(library_dir) and not effective_force:
            wt = skill_git.status(library_dir, env=None)
            if wt == skill_git.GitWorkingTreeStatus.DIRTY:
                click.echo(f"{slug}: dirty — push or use --force to discard")
                had_dirty = True
                continue

        # Full remove: unlink all global symlinks + rmtree library dir + lock entry.
        _remove_all_global_symlinks(slug)
        if library_dir.exists():
            shutil.rmtree(library_dir)
        lock = remove_entry(lock, slug)
        write_lock(lock_path, lock)
        click.echo(f"{slug}: removed")

    if had_dirty:
        ctx.exit(1)


def _remove_all_global_symlinks(slug: str) -> None:
    """Remove the universal bundle link and all non-universal agent links at global scope."""
    bundle_link = _universal_bundle_link(slug)
    if bundle_link.is_symlink():
        bundle_link.unlink()

    for name in AGENTS:
        if name == "universal":
            continue
        cfg = AGENTS[name]
        if cfg.is_universal:
            continue
        link = cfg.global_skills_dir / slug
        if link.is_symlink():
            link.unlink()


def _count_linked(slug: str, scope: str, home: Path | None, project: Path | None) -> str:
    linked = _current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
    )
    return ", ".join(linked[:3]) + ("..." if len(linked) > 3 else "")


skill.add_command(list_cmd)
skill.add_command(status_cmd)
skill.add_command(update_cmd)
skill.add_command(push_cmd)
