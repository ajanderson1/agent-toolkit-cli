"""Derived skill collections; no persisted container or selection state."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_cli.skill_collection_register import discover
from agent_toolkit_cli.skill_collection_transaction import (
    Journal,
    checked_lock,
    link_state,
)
from agent_toolkit_cli.skill_install import InstallError, validate_projection_context
from agent_toolkit_cli.skill_lock import LockEntry, clone_url_from_entry
from agent_toolkit_cli.skill_paths import (
    agent_projection_dir,
    canonical_skill_dir,
    is_skill_projection_available,
    library_lock_path,
    library_skill_path,
    lock_file_path,
    parent_clone_path,
    project_parents_root,
)

CollectionKey = tuple[str, str | None]


@dataclass
class Child:
    slug: str
    entry: LockEntry
    path: Path


@dataclass
class Collection:
    source: str
    ref: str | None
    children: dict[str, Child] = field(default_factory=dict)
    wrapper: str | None = None
    backing: Path | None = None
    error: str = ""

    @property
    def key(self) -> CollectionKey:
        return self.source, self.ref

    @property
    def label(self) -> str:
        return f"{self.source} @ {self.ref or 'default'}"


def projection(
    slug: str, agent: str, *, scope: str, home: Path | None, project: Path | None
) -> Path:
    if agent == "standard" or AGENTS[agent].is_standard:
        return (
            (home or Path.home()) / ".agents/skills" / slug
            if scope == "global"
            else project / ".agents/skills" / slug
        )
    return agent_projection_dir(agent, slug, scope=scope, home=home, project=project)


def _canonical(slug, scope, home, project):
    return canonical_skill_dir(slug, scope=scope, home=home, project=project)


def catalog(*, scope: str, home: Path | None, project: Path | None) -> list[Collection]:
    lib = checked_lock(library_lock_path(home=home))
    scoped = checked_lock(lock_file_path(scope=scope, home=home, project=project))
    universe = {**lib.skills, **scoped.skills}
    groups: dict[CollectionKey, Collection] = {}
    for slug, entry in universe.items():
        canonical = _canonical(slug, scope, home, project)
        if not canonical.exists():
            canonical = library_skill_path(slug, home=home)
        key = entry.source, entry.ref
        if entry.parent_url is not None:
            group = groups.setdefault(key, Collection(*key))
            group.children[slug] = Child(slug, entry, canonical.resolve())
        elif canonical.is_dir() and not (canonical / "SKILL.md").is_file():
            roots = discover(canonical)
            if not roots:
                continue
            group = groups.setdefault(key, Collection(*key))
            if slug in scoped.skills:
                group.wrapper, group.backing = slug, canonical.resolve()
            for root in roots:
                path = root.relative_to(canonical).as_posix()
                names = [
                    n
                    for n, e in universe.items()
                    if (e.source, e.ref, e.skill_path)
                    == (entry.source, entry.ref, path)
                    and e.parent_url is not None
                ]
                name = names[0] if len(names) == 1 else root.name
                child_entry = dataclasses.replace(
                    entry, skill_path=path, parent_url=clone_url_from_entry(entry)
                )
                previous = group.children.get(name)
                if previous is not None and previous.path != root.resolve():
                    group.error = f"Ambiguous child slug {name}: {previous.path} and {root}. Selection is unavailable; choose explicit child identities before installation."
                else:
                    group.children.setdefault(
                        name, Child(name, child_entry, root.resolve())
                    )
    return [g for g in groups.values() if len(g.children) > 1 or g.wrapper is not None]


def exposed(
    child: Child,
    group: Collection,
    agent: str,
    *,
    scope: str,
    home: Path | None,
    project: Path | None,
) -> bool:
    direct = projection(child.slug, agent, scope=scope, home=home, project=project)
    canonical = _canonical(child.slug, scope, home, project)
    if (
        direct.is_symlink()
        and canonical.exists()
        and direct.resolve() == canonical.resolve()
        and (canonical / "SKILL.md").is_file()
    ):
        return True
    if group.wrapper is not None:
        wrapper = projection(
            group.wrapper, agent, scope=scope, home=home, project=project
        )
        if (
            wrapper.is_symlink()
            and group.backing is not None
            and wrapper.resolve() == group.backing
        ):
            return (
                child.path.is_relative_to(group.backing)
                and (child.path / "SKILL.md").is_file()
            )
    return False


def _remaining_wrapper(
    group: Collection, excluded: set[Path], *, scope, home, project
) -> bool:
    for agent in ("standard", *(a for a in AGENTS if not AGENTS[a].is_standard)):
        if not is_skill_projection_available(agent, scope=scope, project=project):
            continue
        path = projection(group.wrapper, agent, scope=scope, home=home, project=project)
        if path not in excluded and (path.exists() or path.is_symlink()):
            return True
    return False


def apply_selection(
    group: Collection,
    selections: dict[str, set[str]],
    *,
    scope: str,
    home: Path | None,
    project: Path | None,
) -> None:
    """Commit complete desired sibling sets for the requested harnesses only."""
    if not selections:
        return
    if group.error:
        raise InstallError(group.error)
    lock_path = lock_file_path(scope=scope, home=home, project=project)
    lock = checked_lock(lock_path)
    journal = Journal()
    links: dict[Path, tuple[Path | None, Path | None]] = {}
    canonicals: dict[Path, tuple[Path | None, Path]] = {}
    before, after = {}, {}
    for agent, selected in selections.items():
        if not selected <= group.children.keys():
            raise InstallError("Unknown collection child in selection")
        validate_projection_context(
            slug=next(iter(group.children)),
            target_agents=(agent,),
            scope=scope,
            home=home,
            project=project,
        )
        roots = {n for n, c in group.children.items() if c.entry.skill_path == "."}
        if roots & selected and selected != set(group.children):
            raise InstallError(
                "Cannot prove independent nested isolation while the real root remains projected for this target; unselect the root first. No files changed."
            )
    backing = group.backing
    if backing is not None:
        wrapper_entry = lock.skills.get(group.wrapper)
        if (
            wrapper_entry is None
            or (wrapper_entry.source, wrapper_entry.ref) != group.key
        ):
            raise InstallError("Legacy wrapper record identity changed")
        if not skill_git.is_git_repo(backing) or not skill_git.remote_matches(
            backing, clone_url_from_entry(wrapper_entry), None
        ):
            raise InstallError(
                f"Cannot prove preserved backing checkout ownership: {backing}"
            )
    # Normal project collections may need their own independent checkout.
    new_parent = None
    if backing is None:
        existing = [
            (_canonical(n, scope, home, project), c) for n, c in group.children.items()
        ]
        found = [(p.resolve(), c) for p, c in existing if p.exists()]
        if found:
            root, child = found[0]
            backing = root
            for _ in (
                Path(child.entry.skill_path).parts
                if child.entry.skill_path != "."
                else ()
            ):
                backing = backing.parent
        else:
            first = next(iter(group.children.values()))
            owner, repo = group.source.split("/", 1)
            backing = parent_clone_path(
                owner,
                repo,
                ref=group.ref,
                root=project_parents_root(project) if scope == "project" else None,
            )
            if not backing.exists():
                store = (
                    library_skill_path("_unused", home=home).parent
                    if scope == "global"
                    else project_parents_root(project)
                )
                if store.is_dir():
                    for candidate in store.iterdir():
                        if (
                            candidate.is_dir()
                            and not candidate.is_symlink()
                            and candidate.name != "_parents"
                            and skill_git.is_git_repo(candidate)
                            and skill_git.remote_matches(
                                candidate, first.entry.parent_url, None
                            )
                        ):
                            raise InstallError(
                                f"Preserved backing {candidate} has incomplete child ownership; possible recovery conflict. Refusing a replacement upstream clone; inspect its remaining records and projections."
                            )
                new_parent = (first.entry.parent_url, backing)
        if backing.exists() and (
            not skill_git.is_git_repo(backing)
            or not skill_git.remote_matches(
                backing, next(iter(group.children.values())).entry.parent_url, None
            )
        ):
            raise InstallError(f"Cannot prove backing checkout ownership: {backing}")
    if (
        group.ref is not None
        and backing.exists()
        and not skill_git._checked_out_at_ref(backing, group.ref, env=None)
    ):
        raise InstallError(
            f"Ref conflict in preserved checkout {backing}; refusing to move it"
        )
    for name, child in group.children.items():
        old = lock.skills.get(name)
        if old is not None and (old.source, old.ref, old.skill_path) != (
            child.entry.source,
            child.entry.ref,
            child.entry.skill_path,
        ):
            raise InstallError(f"{name}: source/ref/path record collision")
        canonical = _canonical(name, scope, home, project)
        private_wrapper = (
            scope == "project" and group.backing is not None
            and not group.backing.resolve().is_relative_to(library_skill_path("_unused", home=home).parent.resolve())
        )
        if private_wrapper:
            # Reconcile an EXISTING private wrapper without turning its data
            # into central library backing or cloning another private checkout.
            from agent_toolkit_cli.skill_paths import project_store_root
            canonical = project_store_root(project) / name
        elif scope == "project":
            from agent_toolkit_cli._paths_core import SKILL_BINDING
            from agent_toolkit_cli.project_backing import check_creation
            check_creation(SKILL_BINDING, name, project, home=home)
        target = backing / child.entry.skill_path
        if not target.resolve().is_relative_to(backing.resolve()):
            raise InstallError(f"{name}: escaping skill path")
        current = link_state(canonical)
        if current is not None and canonical.resolve() != target.resolve():
            raise InstallError(
                f"{name}: canonical target ownership conflict: {canonical}"
            )
        if new_parent is None and not (target / "SKILL.md").is_file():
            raise InstallError(f"{name}: missing SKILL.md in preserved checkout")
        # Register the complete sibling set, without activating unselected siblings.
        before[name], after[name] = old, old or child.entry
        if scope == "project" and old is None:
            after[name] = dataclasses.replace(child.entry, extras={**child.entry.extras,
                "projectBacking": "central" if canonical == library_skill_path(name, home=home) else "isolated"})
        canonicals[canonical] = (current, current or target)
        for agent, selected in selections.items():
            path = projection(name, agent, scope=scope, home=home, project=project)
            current_link = link_state(path)
            if current_link is not None and path.resolve() != target.resolve():
                raise InstallError(f"{name}: projection ownership conflict: {path}")
            desired = (current_link or canonical) if name in selected else None
            if path in links and links[path][1] != desired:
                raise InstallError(
                    f"Shared Standard projection selection conflict: {path}"
                )
            links[path] = current_link, desired
    wrappers = {}
    if group.wrapper is not None:
        for agent in selections:
            path = projection(
                group.wrapper, agent, scope=scope, home=home, project=project
            )
            current = link_state(path)
            if current is not None and path.resolve() != group.backing:
                raise InstallError(f"Wrapper projection ownership conflict: {path}")
            wrappers[path] = current, None
        if not _remaining_wrapper(
            group, set(wrappers), scope=scope, home=home, project=project
        ):
            before[group.wrapper] = lock.skills.get(group.wrapper)
            after[group.wrapper] = None
    guard = dict(before)
    if group.wrapper is not None:
        guard[group.wrapper] = lock.skills.get(group.wrapper)
    journal.expect(lock_path, guard)
    journal.expect_paths([*canonicals, *links, *wrappers])
    try:
        if new_parent is not None:
            # No operator-owned checkout is replaced. Failed clones remain recoverable.
            url, target = new_parent
            if target.exists() or target.is_symlink():
                raise InstallError(f"Backing destination appeared: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            skill_git.clone_pinned_or_branch(url, target, ref=group.ref, env=None)
            if any(
                not (backing / c.entry.skill_path / "SKILL.md").is_file()
                for c in group.children.values()
            ):
                raise InstallError("Registered children missing from acquired checkout")
        for path, (current, target) in canonicals.items():
            journal.link(path, current, target)
        for path, (current, target) in links.items():
            journal.link(path, current, target)
        for path, (current, target) in wrappers.items():
            journal.link(path, current, target)
        journal.write(lock_path, before, after)
        for agent, selected in selections.items():
            for name in group.children:
                link = projection(name, agent, scope=scope, home=home, project=project)
                if link.is_symlink() != (name in selected):
                    raise InstallError(f"Exposure verification failed: {link}")
    except (OSError, InstallError, skill_git.GitError) as exc:
        raise journal.fail(exc) from exc
