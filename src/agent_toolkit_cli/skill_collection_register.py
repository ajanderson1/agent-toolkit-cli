"""Preservation-safe registration of a repository's real skills."""

from __future__ import annotations

import dataclasses
import shutil
import tempfile
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_collection_transaction import (
    Journal,
    checked_lock,
    link_state,
)
from agent_toolkit_cli.skill_install import InstallError
from agent_toolkit_cli.skill_lock import LockEntry
from agent_toolkit_cli.skill_ownership import is_owned_owner
from agent_toolkit_cli.skill_paths import (
    library_lock_path,
    library_skill_path,
    parent_clone_path,
)
from agent_toolkit_cli.skill_source import ParsedSource


def discover(root: Path) -> list[Path]:
    return sorted(
        p.parent
        for p in root.rglob("SKILL.md")
        if not any(part.startswith(".") for part in p.relative_to(root).parts)
        and p.is_file()
        and p.resolve().is_relative_to(root.resolve())
    )


def register(
    parsed: ParsedSource, slug: str | None, *, owned: bool, single: bool = False
) -> bool:
    try:
        return _register(parsed, slug, owned=owned, single=single)
    except (InstallError, OSError, skill_git.GitError) as exc:
        raise click.ClickException(str(exc)) from exc


def _register(
    parsed: ParsedSource, slug: str | None, *, owned: bool, single: bool
) -> bool:
    if parsed.owner_repo is None:
        return False
    owner, repo = parsed.owner_repo.split("/", 1)
    parent = parent_clone_path(owner, repo, ref=parsed.ref)
    journal = Journal()
    with tempfile.TemporaryDirectory(prefix="atk-collection-register-") as tmp:
        discovery_root = parent
        if parent.exists() or parent.is_symlink():
            if not skill_git.is_git_repo(parent) or not skill_git.remote_matches(
                parent, parent_url=parsed.url, env=None
            ):
                raise click.ClickException(
                    f"Unproven backing checkout ownership: {parent}"
                )
            if parsed.ref is not None and not skill_git._checked_out_at_ref(
                parent, parsed.ref, env=None
            ):
                raise click.ClickException(
                    f"Ref conflict in preserved checkout {parent}; refusing to move it"
                )
        else:
            discovery_root = Path(tmp) / "checkout"
            try:
                skill_git.clone_pinned_or_branch(
                    parsed.url, discovery_root, ref=parsed.ref, env=None
                )
            except skill_git.GitError as exc:
                raise click.ClickException(f"parent clone failed: {exc}") from exc
        if single:
            if parsed.subpath is not None:
                roots = [discovery_root / parsed.subpath]
            else:
                from agent_toolkit_cli.commands.skill import (
                    _resolve_skill_name_to_subpath,
                )

                try:
                    subpath = _resolve_skill_name_to_subpath(
                        discovery_root, parsed.skill_name, parsed.owner_repo
                    )
                except click.ClickException as exc:
                    raise click.ClickException(
                        f"{exc}; preserved checkout was not advanced. Use skill update explicitly for upstream changes."
                    ) from exc
                roots = [discovery_root / subpath]
        else:
            roots = discover(discovery_root)
            # Keep the existing flat-root single-skill layout and CLI contract.
            if roots == [discovery_root]:
                return False
            if slug is not None and len(roots) > 1:
                raise click.ClickException(
                    "--slug requires a single skill; use --skill or an explicit path"
                )
        if not roots:
            raise click.ClickException(
                f"{parsed.owner_repo}: no supported SKILL.md files found"
            )
        lock_path = library_lock_path()
        lock = checked_lock(lock_path)
        before, after, targets = {}, {}, {}
        preserved_copies = set()
        for root in roots:
            if (
                not root.resolve().is_relative_to(discovery_root.resolve())
                or not (root / "SKILL.md").is_file()
            ):
                raise click.ClickException(
                    f"{root}: SKILL.md not found in preserved parent; use skill update explicitly for upstream changes"
                )
            path = root.relative_to(discovery_root).as_posix()
            matching = [
                name
                for name, entry in lock.skills.items()
                if entry.source == parsed.owner_repo
                and entry.ref == parsed.ref
                and entry.skill_path == path
                and entry.parent_url is not None
            ]
            if len(matching) > 1:
                raise click.ClickException(
                    f"Ambiguous existing identities for {parsed.owner_repo}/{path}: {matching}"
                )
            if matching and slug is not None and slug != matching[0]:
                raise click.ClickException(
                    f"{slug}: source/ref/path already registered as {matching[0]}; "
                    "refusing to substitute a different recorded slug"
                )
            name = (
                matching[0]
                if matching
                else (slug or parsed.skill_name or (repo if path == "." else root.name))
            )
            if not name or Path(name).name != name or name in (".", ".."):
                raise click.ClickException(f"Unsafe child slug: {name!r}")
            if name in after:
                raise click.ClickException(
                    f"Duplicate skill slug {name!r}; select an explicit path/slug"
                )
            existing = lock.skills.get(name)
            if existing is not None and (
                existing.source,
                existing.ref,
                existing.skill_path,
            ) != (parsed.owner_repo, parsed.ref, path):
                raise click.ClickException(
                    f"{name}: source/ref/path collision; refusing complete batch before writes"
                )
            target = parent / path
            canonical = library_skill_path(name)
            if (
                existing is not None
                and existing.extras.get("materialised") == "copy"
                and canonical.is_dir()
                and not canonical.is_symlink()
            ):
                preserved_copies.add(canonical)
                current = None
            else:
                current = link_state(canonical)
            if current is not None and canonical.resolve() != target.resolve():
                raise click.ClickException(
                    f"{name}: canonical target conflict at {canonical}"
                )
            before[name] = existing
            after[name] = existing or LockEntry(
                source=parsed.owner_repo,
                source_type=parsed.type,
                ref=parsed.ref,
                skill_path=path,
                parent_url=parsed.url,
                upstream_sha=skill_git.head_sha(discovery_root, env=None),
                read_only=not (owned or is_owned_owner(owner)),
            )
            targets[canonical] = (current, target)
        journal.expect(lock_path, before)
        journal.expect_paths(targets)
        try:
            if discovery_root != parent:
                if parent.exists() or parent.is_symlink():
                    raise InstallError(
                        f"Backing checkout appeared during preflight: {parent}"
                    )
                parent.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(discovery_root), str(parent))
            for canonical, (current, target) in targets.items():
                if canonical in preserved_copies:
                    continue
                try:
                    journal.link(canonical, current, current or target)
                except OSError:
                    if (
                        not single
                        or current is not None
                        or link_state(canonical) is not None
                    ):
                        raise
                    if not journal.links or journal.links[-1] != (
                        canonical,
                        None,
                        target,
                    ):
                        raise
                    journal.links.pop()
                    journal.copy(canonical, target)
                    after[canonical.name] = dataclasses.replace(
                        after[canonical.name],
                        extras={**after[canonical.name].extras, "materialised": "copy"},
                    )
            journal.write(lock_path, before, after)
        except (OSError, InstallError) as exc:
            failure = journal.fail(exc)
            # Keep an acquired checkout on failure: recovery must never erase work.
            raise click.ClickException(str(failure)) from exc
        for name in after:
            click.echo(
                f"added {name} to library <- {parsed.owner_repo}/{after[name].skill_path}"
            )
    return True
