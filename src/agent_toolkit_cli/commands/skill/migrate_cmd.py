"""skill migrate-to-monorepo subcommand.

Re-homes owned per-skill lock entries into an owned monorepo: rewrites the
entry to owned-monorepo-subpath shape, replaces the per-skill clone dir with
a symlink into the shared `_parents/` clone, and re-projects harness symlinks.
Refuses (skips) any skill whose local work is not reflected in the monorepo.
See docs/superpowers/specs/2026-05-27-migrate-to-monorepo-design.md.
"""
from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_install import (
    InstallError,
    InstallPlan,
    apply as engine_apply,
)
from agent_toolkit_cli.skill_lock import add_entry, read_lock, write_lock
from agent_toolkit_cli.skill_migrate import (
    check_refusal,
    is_migratable,
    migrated_entry,
    monorepo_subpath_for,
)
from agent_toolkit_cli.skill_paths import (
    library_lock_path,
    library_skill_path,
    parent_clone_path,
)
from agent_toolkit_cli.skill_source import parse_source


def _trees_equal(a: Path, b: Path) -> bool:
    """Recursive content comparison ignoring `.git` (independent histories)."""
    cmp = filecmp.dircmp(a, b, ignore=[".git"])
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(
        a, b, cmp.common_files, shallow=False,
    )
    if mismatch or errors:
        return False
    return all(_trees_equal(a / sub, b / sub) for sub in cmp.common_dirs)


@click.command("migrate-to-monorepo", epilog="""\
One-shot, idempotent, per-machine. Re-homes owned per-skill skills into the
monorepo. Skips any skill with local work not yet in the monorepo.

\b
  agent-toolkit-cli skill migrate-to-monorepo ajanderson1/agent-toolkit
  agent-toolkit-cli skill migrate-to-monorepo ajanderson1/agent-toolkit --dry-run
""")
@click.argument("parent")
@click.option("--dry-run", is_flag=True,
              help="Print the per-skill plan; write nothing.")
def migrate_cmd(parent: str, dry_run: bool) -> None:
    """Re-home owned per-skill skills into an owned monorepo."""
    parsed = parse_source(parent)
    if parsed.owner_repo is None:
        raise click.UsageError("parent must resolve to owner/repo")
    owner, repo = parsed.owner_repo.split("/", 1)

    # file:// test URLs parse as type="git" with a synthetic owner_repo; store
    # their URL so it re-resolves. Real github/gitlab sources store owner/repo.
    parent_source = parsed.url if parsed.type == "git" else parsed.owner_repo
    parent_url = parsed.url

    parent_dir = parent_clone_path(owner, repo, ref=parsed.ref, env=None)
    if not parent_dir.exists():
        parent_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone(parent_url, parent_dir, ref=parsed.ref, env=None)
        except Exception as exc:
            raise click.ClickException(f"parent clone failed: {exc}") from exc
    else:
        try:
            skill_git.fetch(parent_dir, env=None)
        except Exception as exc:
            click.echo(f"warning: parent fetch failed: {exc}", err=True)

    parent_sha = (
        skill_git.head_sha(parent_dir, env=None)
        if skill_git.is_git_repo(parent_dir) else None
    )

    lock_path = library_lock_path()
    lock = read_lock(lock_path)

    migrated: list[str] = []
    skipped: list[tuple[str, str]] = []

    for slug in sorted(lock.skills):
        entry = lock.skills[slug]
        if not is_migratable(entry):
            continue
        subpath = monorepo_subpath_for(slug)
        mono_skill = parent_dir / subpath
        in_monorepo = (mono_skill / "SKILL.md").exists()

        clone = library_skill_path(slug)
        sha_match = (
            skill_git.is_git_repo(clone)
            and entry.upstream_sha is not None
            and skill_git.head_sha(clone, env=None) == entry.upstream_sha
        )
        tree_clean = (
            not skill_git.is_git_repo(clone)
            or skill_git.status(clone, env=None)
            == skill_git.GitWorkingTreeStatus.CLEAN
        )
        content_matches = in_monorepo and _trees_equal(clone, mono_skill)

        reason = check_refusal(
            sha_match=sha_match, tree_clean=tree_clean,
            content_matches=content_matches, in_monorepo=in_monorepo,
        )
        if reason is not None:
            skipped.append((slug, reason.hint))
            continue

        if dry_run:
            migrated.append(slug)
            continue

        # Layer 3: verify the replacement symlink first, then write the
        # (reversible) lock, then do the irreversible delete + swap LAST.
        new_entry = migrated_entry(
            entry, slug=slug, parent_source=parent_source,
            parent_url=parent_url, parent_sha=parent_sha,
        )
        tmp_link = clone.parent / f".{slug}.migrating"
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()
        tmp_link.symlink_to(mono_skill, target_is_directory=True)
        if not (tmp_link / "SKILL.md").exists():
            tmp_link.unlink()
            skipped.append((slug, "symlink verification failed"))
            continue

        # Reversible step first.
        lock = add_entry(lock, slug, new_entry)
        write_lock(lock_path, lock)

        # Irreversible step last.
        shutil.rmtree(clone)
        tmp_link.rename(clone)

        try:
            engine_apply(
                InstallPlan(slug=slug, scope="global", source=None, ref=None,
                            add_agents=(), remove_agents=()),
                home=None, project=None, env=None,
            )
        except InstallError as exc:
            click.echo(f"warning: reproject {slug} failed: {exc}", err=True)

        migrated.append(slug)

    _report(migrated, skipped, dry_run)


def _report(
    migrated: list[str], skipped: list[tuple[str, str]], dry_run: bool,
) -> None:
    prefix = "Would migrate" if dry_run else "Migrated"
    if migrated:
        click.echo(f"{prefix} {len(migrated)}: {', '.join(migrated)}")
    if skipped:
        click.echo(f"Skipped {len(skipped)}:")
        for slug, hint in skipped:
            click.echo(f"  {slug} — {hint}")
    if not migrated and not skipped:
        click.echo("Nothing to migrate (no owned per-skill entries).")
