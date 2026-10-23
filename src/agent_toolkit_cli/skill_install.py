"""Canonical-clone + per-agent symlink projection, catalog-aware.

v2.2 library/install split:
  Library canonical: $AGENT_TOOLKIT_SKILLS_ROOT/<slug>/  (global-only, git tree)
  Project canonical: <project>/.agents/skills/<slug>/    (independent git clone)

Symlink rules (v2.2, mirroring installer.ts:280-323):
  - Global + "standard" bundle target  → ~/.agents/skills/<slug> → library
  - Global + non-standard agent         → ~/.<agent-dir>/skills/<slug> → library
  - Project + standard agent            → symlink → external canonical (store)
  - Project + non-standard              → <project>/<agent-dir>/skills/<slug> → canonical
                                          (agent root dir is created if absent)

v3.0.0 facade split (PR1):
  Asset-type-agnostic install primitives (errors, dataclasses, plan(),
  _current_linked_agents, _should_skip_symlink, _symlink_or_copy,
  _doctor_hint) live in `_install_core`. This module re-exports them and
  injects the skill-specific bundle-link helpers (`_standard_bundle_link`,
  `_project_standard_link`) when delegating to the core. The .agents/skills
  path that defines skill standardness is owned here.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Literal

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.paperclip_paths import (
    PaperclipContextError,
    require_paperclip_company,
)
from agent_toolkit_cli._install_core import (
    DirtyCanonicalError,  # noqa: F401  re-exported for callers
    InstallError,
    InstallPlan,
    InstallResult,
    LockMismatchError,
    _current_linked_agents as _core_current_linked_agents,
    _doctor_hint,
    _should_skip_symlink,
    _symlink_or_copy,  # noqa: F401  re-exported for callers
    plan as _core_plan,
)
from agent_toolkit_cli.skill_agents import (  # noqa: F401  re-exported (preserves pre-refactor public surface)
    AGENTS,
    UnknownAgentError,
    get_agent,
)
from agent_toolkit_cli.skill_paths import (
    Scope,
    agent_projection_dir,
    canonical_skill_dir,
    lock_file_path,
)
from agent_toolkit_cli.skill_source import ParsedSource

# Catalog tokens that are virtual entries, not real harness symlink targets.
_SKILL_SYNTHETIC_NAMES: frozenset[str] = frozenset({"standard", "standard-skill"})


def _standard_bundle_link(slug: str) -> Path:
    """The ~/.agents/skills/<slug> path used for standard-bundle installs at global scope."""
    return Path.home() / ".agents" / "skills" / slug


def validate_projection_context(
    *,
    slug: str,
    target_agents: Iterable[str],
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> None:
    """Fail loudly on an invalid Paperclip projection before any mutation.

    A no-op unless ``paperclip`` is a target. When it is, this refuses
    traversal-like slugs, non-project scope, a missing company context, a
    symlinked projection ancestor that could redirect outside the instance
    tree, and a conflicting real file/foreign symlink at the destination.
    Running this before canonical materialization or lock writes guarantees a
    rejected install leaves no project canonical or lock entry behind.
    """
    agents = tuple(target_agents)
    if "paperclip" not in agents:
        return
    if (
        not slug
        or slug in {".", ".."}
        or Path(slug).name != slug
        or Path(slug).is_absolute()
    ):
        raise InstallError(
            f"{slug!r}: Paperclip skill slug must be one non-empty leaf name"
        )
    if scope != "project" or project is None:
        raise InstallError(
            "paperclip: company-scoped skills require project scope inside "
            "~/.paperclip/instances/<instance>/companies/<company-id>"
        )
    try:
        context = require_paperclip_company(project)
    except PaperclipContextError as exc:
        raise InstallError(f"paperclip: {exc}") from exc
    canonical = canonical_skill_dir(
        slug, scope="project", home=home, project=project,
    )
    destination = context.skills_root / slug
    # Paperclip's instance/company library is expected to be a real directory
    # chain. Reject an existing symlinked ancestor rather than following a
    # redirect outside the instance tree. Missing parents remain creatable.
    for ancestor in (context.instance_root / "skills", context.skills_root):
        if ancestor.is_symlink():
            raise InstallError(
                f"{slug}/paperclip: symlinked projection parent is unsupported: "
                f"{ancestor}"
            )
    try:
        destination.parent.resolve(strict=False).relative_to(
            (context.instance_root / "skills").resolve(strict=False)
        )
    except ValueError as exc:
        raise InstallError(
            f"{slug}/paperclip: projection escapes the instance skills root"
        ) from exc
    if destination.is_symlink():
        if destination.resolve() != canonical.resolve():
            raise InstallError(
                f"{slug}/paperclip: conflicting symlink at {destination}: "
                f"points to {destination.resolve()}, expected {canonical}"
            )
    elif destination.exists():
        raise InstallError(
            f"{slug}/paperclip: conflicting non-symlink at {destination}; "
            "refusing to overwrite"
        )


def _project_standard_link(project: Path, slug: str) -> Path:
    """The <project>/.agents/skills/<slug> path for the standard bundle at project scope.

    Every standard agent (skills_dir == ".agents/skills") reads through this one
    shared projection. Mirrors _standard_bundle_link at project scope: under the
    external-store model it is a symlink → the project canonical, created/removed
    by the synthetic "standard" token in apply()."""
    return project / ".agents" / "skills" / slug


def plan(
    *,
    slug: str,
    scope: Scope,
    source: ParsedSource | None = None,
    ref: str | None = None,
    target_agents: Iterable[str] = (),
    home: Path | None = None,
    project: Path | None = None,
) -> InstallPlan:
    """Compute the minimal add/remove delta to reach target_agents.

    Thin facade over `_install_core.plan` that binds the skill-specific
    `_standard_bundle_link` helper. Pure: reads current symlinks on disk +
    lock, returns plan. The skip rules from apply() are NOT applied here —
    plan reflects user intent ('I want codex globally'), apply realises it
    ('codex is standard so no symlink needed').
    """
    # Materialize once: target_agents may be a one-shot generator that both the
    # validator and the core plan would otherwise consume.
    agents = tuple(target_agents)
    validate_projection_context(
        slug=slug, target_agents=agents, scope=scope, home=home, project=project,
    )
    return _core_plan(
        slug=slug, scope=scope, source=source, ref=ref,
        target_agents=agents, home=home, project=project,
        canonical_dir_resolver=canonical_skill_dir,
        standard_bundle_link=_standard_bundle_link,
        synthetic_names=_SKILL_SYNTHETIC_NAMES,
    )


def _current_linked_agents(
    *, slug: str, scope: Scope,
    home: Path | None, project: Path | None,
) -> tuple[str, ...]:
    """Return agents whose symlink currently resolves to our canonical.

    Thin facade over `_install_core._current_linked_agents` that binds the
    skill-specific `_standard_bundle_link` helper so the synthetic
    "standard" bundle token is recognised at global scope.
    """
    return _core_current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
        canonical_dir_resolver=canonical_skill_dir,
        standard_bundle_link=_standard_bundle_link,
        synthetic_names=_SKILL_SYNTHETIC_NAMES,
    )


def apply(
    plan: InstallPlan, *, home: Path | None = None,
    project: Path | None = None, env: dict[str, str] | None = None,
) -> InstallResult:
    from agent_toolkit_cli.project_backing import new_install_paths, cleanup_created_paths
    with new_install_paths() as created:
        result = _apply(plan, home=home, project=project, env=env, _created_paths=created)
        if plan.scope == "project" and any(path == result.canonical_path for path, _dev, _ino in created):
            from agent_toolkit_cli.skill_lock import read_lock
            if plan.slug not in read_lock(lock_file_path(scope="project", project=project)).skills:
                cleanup_created_paths(created)
        return result


def _apply(
    plan: InstallPlan,
    *,
    home: Path | None = None,
    project: Path | None = None,
    env: dict[str, str] | None = None,
    _created_paths=None,
) -> InstallResult:
    """Execute the plan; retain only successfully registered new state."""
    from agent_toolkit_cli.project_backing import create_backing_dir, record_created_path
    from agent_toolkit_cli.skill_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )

    # apply() handles only single-skill (repo-root) sources: it clones the
    # source flat into the canonical and records skillPath="SKILL.md" with no
    # parentUrl. A source carrying a subpath is a monorepo source, which would
    # be cloned and recorded incorrectly here. Monorepo entries are written by
    # commands.skill._add_monorepo (which always builds its plan with
    # source=None), so a monorepo source reaching apply() is internal misuse —
    # refuse it loudly before any clone happens.
    if plan.source is not None and plan.source.subpath:
        raise InstallError(
            f"{plan.slug}: apply() cannot install a monorepo source "
            f"(subpath={plan.source.subpath!r}); monorepo skills are installed "
            f"by the monorepo add path. This is an internal misuse of apply()."
        )

    # Direct engine callers (including project-scope removals) get the same
    # fail-loud Paperclip ownership contract before any canonical/lock work.
    validate_projection_context(
        slug=plan.slug,
        target_agents=(*plan.add_agents, *plan.remove_agents),
        scope=plan.scope,
        home=home,
        project=project,
    )

    if plan.scope == "project" and (plan.add_agents or plan.source is not None):
        from agent_toolkit_cli._paths_core import SKILL_BINDING
        from agent_toolkit_cli.project_backing import check_creation
        check_creation(SKILL_BINDING, plan.slug, project, home=home)
        if plan.source is None:
            from agent_toolkit_cli.skill_paths import library_lock_path
            ensure_project_canonical(slug=plan.slug, project=project, global_lock_path=library_lock_path(), write_entry=False, _created_paths=_created_paths)
    canonical = canonical_skill_dir(
        plan.slug, scope=plan.scope, home=home, project=project,
    )
    lock_path = lock_file_path(scope=plan.scope, home=home, project=project)
    lock = read_lock(lock_path)
    existing_entry = lock.skills.get(plan.slug)

    # Clone canonical if needed.
    if plan.source is not None and not canonical.exists():
        create_backing_dir(canonical, _created_paths)
        skill_git.clone_pinned_or_branch(
            plan.source.url, canonical, ref=plan.ref, env=env,
        )
    elif plan.source is not None and existing_entry is not None:
        requested = plan.source.identity
        if existing_entry.source != requested:
            raise LockMismatchError(
                f"{plan.slug}: canonical exists with source "
                f"{existing_entry.source!r}; refusing to overwrite with "
                f"{requested!r}. Run `skill remove {plan.slug}` first."
            )

    # Add symlinks (honoring skip rules).
    created: list[Path] = []
    skipped: list[str] = []
    for name in plan.add_agents:
        # The synthetic "standard" token means: create ~/.agents/skills/<slug>
        # → library at global scope; at project scope it's a no-op (the project
        # canonical IS the install).
        if name == "standard":
            # The standard bundle is one shared projection symlink that all
            # standard agents read through: ~/.agents/skills/<slug> at global
            # scope, <project>/.agents/skills/<slug> at project scope. Under the
            # external-store model both point at the (out-of-tree) canonical.
            link = (
                _standard_bundle_link(plan.slug)
                if plan.scope == "global"
                else _project_standard_link(project, plan.slug)
            )
            link.parent.mkdir(parents=True, exist_ok=True)
            if link == canonical and link.is_dir() and not link.is_symlink():
                # A recorded pre-external-store install is its own projection.
                # Keep it intact until explicit central migration.
                continue
            if link.is_symlink():
                if link.resolve() != canonical.resolve():
                    raise InstallError(
                        f"{plan.slug}/standard: conflicting symlink at {link}: "
                        f"points to {link.resolve()}, expected {canonical}"
                        + _doctor_hint(plan.slug, plan.scope)
                    )
            elif link.exists():
                raise InstallError(
                    f"{plan.slug}/standard: conflicting non-symlink at {link}; "
                    f"refusing to overwrite"
                )
            else:
                link.symlink_to(canonical)
                created.append(link)
                record_created_path(link, _created_paths)
            continue

        skip, reason = _should_skip_symlink(
            agent_name=name, scope=plan.scope, project=project,
        )
        if skip:
            skipped.append(name)
            continue
        link = agent_projection_dir(
            name, plan.slug, scope=plan.scope, home=home, project=project,
        )
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            target = link.resolve()
            if target != canonical.resolve():
                raise InstallError(
                    f"{plan.slug}/{name}: conflicting symlink at {link}: "
                    f"points to {target}, expected {canonical}"
                    + _doctor_hint(plan.slug, plan.scope)
                )
        elif link.exists():
            raise InstallError(
                f"{plan.slug}/{name}: conflicting non-symlink at {link}; "
                f"refusing to overwrite"
            )
        else:
            link.symlink_to(canonical)
            created.append(link)
            record_created_path(link, _created_paths)

    # Remove symlinks.
    removed: list[Path] = []
    for name in plan.remove_agents:
        if name == "standard":
            link = (
                _standard_bundle_link(plan.slug)
                if plan.scope == "global"
                else _project_standard_link(project, plan.slug)
            )
            if link.is_symlink():
                link.unlink()
                removed.append(link)
            elif link.exists():
                raise InstallError(
                    f"{plan.slug}/standard: cannot unlink {link}: not a symlink"
                )
            continue

        skip, _ = _should_skip_symlink(
            agent_name=name, scope=plan.scope, project=project,
        )
        if skip:
            # No symlink exists; remove-from-canonical handled by caller.
            continue
        link = agent_projection_dir(
            name, plan.slug, scope=plan.scope, home=home, project=project,
        )
        if link.is_symlink():
            link.unlink()
            removed.append(link)
        elif link.exists():
            raise InstallError(
                f"{plan.slug}/{name}: cannot unlink {link}: not a symlink"
            )

    # Update lock.
    lock_action: Literal["added", "updated", "unchanged"] = "unchanged"
    if plan.source is not None:
        # Monorepo sources were refused at the top of apply(); only
        # single-skill (repo-root) sources reach here, so skillPath="SKILL.md"
        # is correct.
        if skill_git.is_git_repo(canonical):
            upstream_sha = skill_git.remote_head_sha(
                canonical,
                ref=skill_git.resolve_ref(plan.ref, canonical, env=env),
                env=env,
            )
            local_sha = skill_git.head_sha(canonical, env=env)
        else:
            upstream_sha = None
            local_sha = None
        entry = LockEntry(
            source=plan.source.identity,
            source_type=plan.source.type,
            ref=plan.ref,
            skill_path="SKILL.md",
            upstream_sha=upstream_sha,
            local_sha=local_sha,
            extras={"projectBacking": "central" if canonical == canonical_skill_dir(plan.slug, scope="global", home=home) else "isolated"} if plan.scope == "project" else {},
        )
        write_lock(lock_path, add_entry(lock, plan.slug, entry))
        lock_action = "added" if existing_entry is None else "updated"

    if plan.scope == "project" and plan.source is None and existing_entry is None and plan.add_agents and len(skipped) < len(plan.add_agents):
        from dataclasses import replace
        from agent_toolkit_cli.skill_paths import library_lock_path
        global_entry = read_lock(library_lock_path()).skills.get(plan.slug)
        if global_entry is not None:
            entry = replace(global_entry, upstream_sha=None, local_sha=None,
                extras={**global_entry.extras, "projectBacking": "central" if canonical == canonical_skill_dir(plan.slug, scope="global", home=home) else "isolated"})
            write_lock(lock_path, add_entry(lock, plan.slug, entry))
            lock_action = "added"

    return InstallResult(
        plan=plan,
        canonical_path=canonical,
        created=tuple(created),
        removed=tuple(removed),
        skipped=tuple(skipped),
        lock_action=lock_action,
    )


def migrate_project_canonical(*, project: Path, slug: str) -> None:
    """Migrate an old in-tree project canonical to the external store.

    Idempotent. Old layout put the canonical at <project>/.agents/skills/<slug>
    as a real clone (single-skill) or a symlink into the in-tree _parents/ cache
    (v2.9.0 monorepo). The new layout keeps the canonical in the external store
    (project_store_root) and leaves only a projection symlink in the tree.

    - Old is already a symlink into the store: no-op (already migrated).
    - Old is any other symlink (v2.9.0 monorepo, or stale): remove it; the
      installer recreates the new-layout symlink and re-clones the parent into
      the store's _parents/.
    - Old is a real directory (single-skill clone, possibly dirty): if the
      store dest already exists, rename it to <slug>.bak-<UTC-timestamp> first
      (never overwrite); then move the clone into the store (git history + dirty
      work travel intact); leave a symlink behind so stale references resolve.
    """
    import datetime

    from agent_toolkit_cli.skill_paths import project_store_root

    old = project / ".agents" / "skills" / slug
    if not old.is_symlink() and not old.exists():
        return  # nothing to migrate

    dest = project_store_root(project) / slug

    if old.is_symlink():
        try:
            resolved = old.resolve()
        except OSError:
            resolved = None
        if resolved is not None and resolved == dest.resolve():
            return  # already migrated → no-op
        old.unlink()  # v2.9.0 monorepo symlink / stale: holds no work
        return

    # old is a real directory: move it into the store.
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = dest.parent / f"{slug}.bak-{ts}"
        shutil.move(str(dest), str(backup))
        click.echo(
            f"{slug}: existing store entry backed up to {backup} before migration"
        )
    shutil.move(str(old), str(dest))
    old.parent.mkdir(parents=True, exist_ok=True)
    old.symlink_to(dest)


def ensure_project_canonical(
    *,
    slug: str,
    project: Path,
    global_lock_path: Path,
    env: dict[str, str] | None = None,
    write_entry: bool = True,
    _created_paths=None,
) -> Path:
    """If <project>/.agents/skills/<slug>/ doesn't exist, clone it from the
    global library lock's recorded source URL. Returns the canonical path.

    For monorepo skills (global lock entry has parent_url set), clones the
    parent repo into a project-local _parents/ cache and symlinks the
    canonical into parent/<skillPath>, mirroring the global library layout.

    Also writes the project lock entry if absent (same guarantee the CLI's
    install_cmd provides, so both call sites get a fully-ready project canonical).

    Raises InstallError if the slug is not in the global library lock and the
    install is not already complete at project scope.
    """
    from agent_toolkit_cli.project_backing import new_install_paths, create_backing_dir, record_created_path
    if _created_paths is None:
        with new_install_paths() as created:
            return ensure_project_canonical(slug=slug, project=project,
                global_lock_path=global_lock_path, env=env, write_entry=write_entry, _created_paths=created)
    from agent_toolkit_cli.skill_lock import (
        LockEntry, add_entry, clone_url_from_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.skill_paths import (
        canonical_skill_dir, lock_file_path, parent_clone_path, project_parents_root,
    )

    # Selection is shared with the TUI and all engine entry points. Never
    # automatically move/remove an old in-tree or external private checkout.
    from agent_toolkit_cli._paths_core import SKILL_BINDING
    from agent_toolkit_cli.project_backing import check_creation, ensure
    project_canonical = check_creation(SKILL_BINDING, slug, project)
    from agent_toolkit_cli.skill_paths import library_skill_path
    if project_canonical == library_skill_path(slug):
        return ensure(SKILL_BINDING, slug, project, write_entry=write_entry, created_paths=_created_paths)
    # Existing private work is usable irrespective of rollout configuration.
    # Only missing backing requires deliberately enabled legacy creation.
    if not project_canonical.exists():
        from agent_toolkit_cli.behavior import project_backing
        if project_backing() != "isolated":
            raise InstallError(f"{slug}: private backing missing; restore it or explicitly migrate to central")

    # Already fully installed at project scope (canonical on disk + project
    # lock entry)? Nothing to ensure — return without consulting the global
    # lock. This keeps `unlisted` installs (project entry whose slug was
    # removed from the library, #360) operable: Apply must not fail on rows
    # that need no materialisation. A broken canonical symlink fails the
    # .exists() check and falls through to the normal (fail-loud) path.
    if project_canonical.exists():
        project_lock_path = lock_file_path(scope="project", project=project)
        if slug in read_lock(project_lock_path).skills:
            return project_canonical

    global_lock = read_lock(global_lock_path)
    entry = global_lock.skills.get(slug)
    if entry is None:
        raise InstallError(f"{slug}: not in global library")
    from agent_toolkit_cli.project_backing import _validate_entry
    _validate_entry(entry, slug)

    if entry.parent_url is not None:
        # Monorepo skill: clone the parent into the project-local _parents/
        # cache and symlink the canonical into parent/<skillPath>, mirroring
        # the global library layout.
        if entry.skill_path is None:
            raise InstallError(
                f"{slug}: monorepo lock entry missing skillPath"
            )
        parts = entry.source.split("/", 1)
        if len(parts) != 2:
            raise InstallError(
                f"{slug}: monorepo lock entry has non-owner/repo source "
                f"{entry.source!r}"
            )
        owner, repo = parts
        parent_dir = parent_clone_path(
            owner, repo, ref=entry.ref,
            root=project_parents_root(project), env=env,
        )
        if not parent_dir.exists():
            create_backing_dir(parent_dir, _created_paths)
            # Cache key (parent_clone_path above) stays on the raw ref; the
            # clone honours a SHA pin via clone-at-HEAD + checkout (#345).
            skill_git.clone_pinned_or_branch(
                entry.parent_url, parent_dir, ref=entry.ref, env=env,
            )
        else:
            try:
                skill_git.fetch(parent_dir, env=env)
            except Exception:  # noqa: BLE001
                pass  # offline / no remote — the existing clone is still usable
        skill_root = parent_dir / entry.skill_path
        if not (skill_root / "SKILL.md").exists():
            raise InstallError(
                f"{slug}: {entry.skill_path}/SKILL.md not found in parent "
                f"clone at {parent_dir}"
            )
        if not project_canonical.exists() and not project_canonical.is_symlink():
            project_canonical.parent.mkdir(parents=True, exist_ok=True)
            project_canonical.symlink_to(skill_root)
            record_created_path(project_canonical, _created_paths)
        if project_canonical.is_symlink() and not project_canonical.exists():
            raise InstallError(
                f"{slug}: canonical symlink at {project_canonical} is broken "
                f"(parent clone missing). Run `skill doctor -p` to repair."
            )
    elif not project_canonical.exists():
        # Single-skill repo: clone the repo root flat into the canonical dir.
        create_backing_dir(project_canonical, _created_paths)
        source_url = clone_url_from_entry(entry)
        skill_git.clone_pinned_or_branch(
            source_url, project_canonical, ref=entry.ref, env=env,
        )

    project_lock_path = lock_file_path(scope="project", project=project)
    project_lock = read_lock(project_lock_path)
    if write_entry and slug not in project_lock.skills:
        proj_entry = LockEntry(
            source=entry.source,
            source_type=entry.source_type,
            ref=entry.ref,
            skill_path=entry.skill_path,
            upstream_sha=None,
            local_sha=None,
            parent_url=entry.parent_url,
            read_only=entry.read_only,
        )
        write_lock(project_lock_path, add_entry(project_lock, slug, proj_entry))

    return project_canonical


def apply_collection_selection(group, selections, *, scope, home=None, project=None) -> None:
    """Apply complete sibling selections before ordinary per-slug materialization."""
    from agent_toolkit_cli.skill_collections import apply_selection
    apply_selection(group, selections, scope=scope, home=home, project=project)


# ── Legacy v2.0.0 wrappers ──────────────────────────────────────────────
# These continue to accept the 5-harness shortcut names and delegate to
# plan()+apply() using skills.sh agent names.

from agent_toolkit_cli.skill_paths import _SHORTCUT_TO_AGENT  # noqa: E402


def install(
    *,
    parsed: ParsedSource,
    slug: str,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
    env: dict[str, str] | None,
) -> Path:
    """Legacy 5-harness shortcut entry point; delegates to plan()+apply()."""
    canonical = canonical_skill_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists() and skill_git.is_git_repo(canonical):
        skill_git.fetch(canonical, env=env)
        try:
            skill_git.merge(
                canonical,
                ref=skill_git.resolve_ref(parsed.ref, canonical, env=env),
                env=env,
            )
        except skill_git.GitError:
            pass

    target_agents = tuple(_SHORTCUT_TO_AGENT[h] for h in harnesses)
    p = plan(
        slug=slug, scope=scope,
        source=parsed, ref=parsed.ref,
        target_agents=target_agents,
        home=home, project=project,
    )
    apply(p, home=home, project=project, env=env)
    return canonical


def uninstall(
    *,
    slug: str,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
) -> None:
    """Legacy shortcut: detach projects (retaining private provenance); global full removal."""
    p = plan(
        slug=slug, scope=scope,
        source=None, ref=None,
        target_agents=(),
        home=home, project=project,
    )
    apply(p, home=home, project=project, env=None)

    if scope == "project":
        # Detach private backing without forgetting the provenance needed to
        # reinstall it while new isolation is disabled. Central projections
        # can drop their scope-only registration.
        from agent_toolkit_cli.skill_lock import read_lock, remove_entry, write_lock

        lock_path = lock_file_path(scope="project", project=project)
        lock = read_lock(lock_path)
        if (slug in lock.skills and canonical_skill_dir(slug, scope="project", home=home, project=project) == canonical_skill_dir(slug, scope="global", home=home)):
            write_lock(lock_path, remove_entry(lock, slug))
        return

    canonical = canonical_skill_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists():
        shutil.rmtree(canonical)
