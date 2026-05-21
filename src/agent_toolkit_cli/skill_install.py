"""Canonical-clone + per-agent symlink projection, catalog-aware.

v2.2 library/install split:
  Library canonical: $AGENT_TOOLKIT_SKILLS_ROOT/<slug>/  (global-only, git tree)
  Project canonical: <project>/.agents/skills/<slug>/    (independent git clone)

Symlink rules (v2.2, mirroring installer.ts:280-323):
  - Global + "universal" bundle target  → ~/.agents/skills/<slug> → library
  - Global + non-universal agent        → ~/.<agent-dir>/skills/<slug> → library
  - Project + universal agent           → no symlink (canonical IS the install)
  - Project + non-universal             → <project>/<agent-dir>/skills/<slug> → canonical
                                          (agent root dir is created if absent)
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_agents import (
    AGENTS, UnknownAgentError, get_agent, is_universal,
)
from agent_toolkit_cli.skill_paths import (
    Scope,
    agent_projection_dir,
    canonical_skill_dir,
    library_skill_path,
    lock_file_path,
)
from agent_toolkit_cli.skill_source import ParsedSource


class InstallError(RuntimeError):
    """Base error for install failures."""


class LockMismatchError(InstallError):
    """Canonical exists on disk but lock entry source differs from request."""


class DirtyCanonicalError(InstallError):
    """Full-remove requested against dirty canonical without --force."""


def _symlink_or_copy(src: Path, dest: Path) -> str:
    """Materialise `dest` to refer to `src`. Try symlink; fall back to copy.

    Returns 'symlink' or 'copy' so the caller can record the materialisation
    mode in the lock entry's extras (relevant for `update`: copy-mode needs
    re-copy, symlink-mode just needs the parent to be re-pulled).
    """
    if dest.exists() or dest.is_symlink():
        raise InstallError(
            f"{dest}: refusing to overwrite existing path"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.symlink_to(src, target_is_directory=True)
        return "symlink"
    except OSError:
        shutil.copytree(src, dest)
        return "copy"


@dataclass(frozen=True)
class InstallPlan:
    slug: str
    scope: Scope
    source: ParsedSource | None
    ref: str | None
    add_agents: tuple[str, ...]
    remove_agents: tuple[str, ...]

    def is_noop(self) -> bool:
        return (self.source is None
                and not self.add_agents
                and not self.remove_agents)


@dataclass(frozen=True)
class InstallResult:
    plan: InstallPlan
    canonical_path: Path
    created: tuple[Path, ...]
    removed: tuple[Path, ...]
    skipped: tuple[str, ...]  # agents whose symlink was intentionally skipped
    lock_action: Literal["added", "updated", "unchanged"]


def _should_skip_symlink(
    *, agent_name: str, scope: Scope, project: Path | None,
) -> tuple[bool, str]:
    """Return (skip?, reason). Mirrors installer.ts:296-323 with v2.2 adjustments.

    v2.2 semantics:
      - Global + universal: NOT skipped. We create ~/.agents/skills/<slug> → library.
      - Project + universal: SKIPPED. The project canonical at
        <project>/.agents/skills/<slug>/ IS the install; no symlink needed.
      - Global + non-universal: NOT skipped (symlink → library).
      - Project + non-universal: NOT skipped. The agent root dir is auto-created
        by apply() via link.parent.mkdir(parents=True, exist_ok=True).

    The special "universal" bundle token is handled in apply() before
    _should_skip_symlink is called; it never reaches here as an agent_name.
    """
    cfg = get_agent(agent_name)
    if cfg.is_universal:
        # Project canonical IS the universal-agent install path — no symlink.
        if scope == "project":
            return True, "universal-project"
        # Global universal agents get a symlink ~/.agents/skills/<slug> → library,
        # created via the universal bundle path in apply(). Per-agent universal
        # symlinks (e.g. cfg.global_skills_dir) resolve through ~/.agents/skills/
        # already at the OS level, so we skip the redundant per-agent write.
        return True, "universal-global"
    return False, ""


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

    Pure: reads current symlinks on disk + lock, returns plan. The skip
    rules from apply() are NOT applied here — plan reflects user intent
    ('I want codex globally'), apply realises it ('codex is universal so
    no symlink needed')."""
    for n in target_agents:
        if n not in AGENTS:
            raise UnknownAgentError(n)
    current = _current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
    )
    target = tuple(target_agents)
    add = tuple(n for n in target if n not in current)
    remove = tuple(n for n in current if n not in target)
    return InstallPlan(
        slug=slug, scope=scope, source=source, ref=ref,
        add_agents=add, remove_agents=remove,
    )


def _current_linked_agents(
    *, slug: str, scope: Scope,
    home: Path | None, project: Path | None,
) -> tuple[str, ...]:
    """Return agents whose symlink currently resolves to our canonical.

    Includes the "universal" bundle token at global scope if
    ~/.agents/skills/<slug> is a symlink to the library canonical.

    For project-scope universal agents (the only skipped case at project scope),
    'currently linked' means the project canonical directory exists.
    """
    canonical = canonical_skill_dir(
        slug, scope=scope, home=home, project=project,
    )
    canonical_real = canonical.resolve() if canonical.exists() else canonical
    canonical_exists = canonical.exists()

    linked: list[str] = []

    # Check universal bundle token separately at global scope.
    if scope == "global":
        bundle_link = _universal_bundle_link(slug)
        if bundle_link.is_symlink() and bundle_link.resolve() == canonical_real:
            linked.append("universal")

    for name in AGENTS:
        # Skip the synthetic 'universal' entry — handled above via bundle link.
        if name == "universal":
            continue

        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            # For project-scope universal agents, 'linked' means canonical exists.
            if scope == "project" and canonical_exists:
                linked.append(name)
            continue

        link = agent_projection_dir(
            name, slug, scope=scope, home=home, project=project,
        )
        if link.is_symlink() and link.resolve() == canonical_real:
            linked.append(name)
    return tuple(linked)


def _universal_bundle_link(slug: str) -> Path:
    """The ~/.agents/skills/<slug> path used for universal-bundle installs at global scope."""
    return Path.home() / ".agents" / "skills" / slug


def apply(
    plan: InstallPlan,
    *,
    home: Path | None = None,
    project: Path | None = None,
    env: dict[str, str] | None = None,
) -> InstallResult:
    """Execute the plan."""
    from agent_toolkit_cli.skill_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )

    canonical = canonical_skill_dir(
        plan.slug, scope=plan.scope, home=home, project=project,
    )
    lock_path = lock_file_path(scope=plan.scope, home=home, project=project)
    lock = read_lock(lock_path)
    existing_entry = lock.skills.get(plan.slug)

    # Clone canonical if needed.
    if plan.source is not None and not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(plan.source.url, canonical, ref=plan.ref, env=env)
    elif plan.source is not None and existing_entry is not None:
        requested = plan.source.owner_repo or plan.source.url
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
        # The synthetic "universal" token means: create ~/.agents/skills/<slug>
        # → library at global scope; at project scope it's a no-op (the project
        # canonical IS the install).
        if name == "universal":
            if plan.scope == "global":
                link = _universal_bundle_link(plan.slug)
                link.parent.mkdir(parents=True, exist_ok=True)
                if link.is_symlink():
                    if link.resolve() != canonical.resolve():
                        raise InstallError(
                            f"{plan.slug}/universal: conflicting symlink at {link}: "
                            f"points to {link.resolve()}, expected {canonical}"
                        )
                elif link.exists():
                    raise InstallError(
                        f"{plan.slug}/universal: conflicting non-symlink at {link}; "
                        f"refusing to overwrite"
                    )
                else:
                    link.symlink_to(canonical)
                    created.append(link)
            else:
                # Project scope: project canonical exists → universal is already installed.
                skipped.append(name)
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
                )
        elif link.exists():
            raise InstallError(
                f"{plan.slug}/{name}: conflicting non-symlink at {link}; "
                f"refusing to overwrite"
            )
        else:
            link.symlink_to(canonical)
            created.append(link)

    # Remove symlinks.
    removed: list[Path] = []
    for name in plan.remove_agents:
        if name == "universal":
            if plan.scope == "global":
                link = _universal_bundle_link(plan.slug)
                if link.is_symlink():
                    link.unlink()
                    removed.append(link)
                elif link.exists():
                    raise InstallError(
                        f"{plan.slug}/universal: cannot unlink {link}: not a symlink"
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
        if skill_git.is_git_repo(canonical):
            upstream_sha = skill_git.remote_head_sha(
                canonical, ref=plan.ref or "main", env=env,
            )
            local_sha = skill_git.head_sha(canonical, env=env)
        else:
            upstream_sha = None
            local_sha = None
        entry = LockEntry(
            source=plan.source.owner_repo or plan.source.url,
            source_type=plan.source.type,
            ref=plan.ref,
            skill_path="SKILL.md",
            upstream_sha=upstream_sha,
            local_sha=local_sha,
        )
        write_lock(lock_path, add_entry(lock, plan.slug, entry))
        lock_action = "added" if existing_entry is None else "updated"

    return InstallResult(
        plan=plan,
        canonical_path=canonical,
        created=tuple(created),
        removed=tuple(removed),
        skipped=tuple(skipped),
        lock_action=lock_action,
    )


def ensure_project_canonical(
    *,
    slug: str,
    project: Path,
    global_lock_path: Path,
    env: dict[str, str] | None = None,
) -> Path:
    """If <project>/.agents/skills/<slug>/ doesn't exist, clone it from the
    global library lock's recorded source URL. Returns the canonical path.

    Also writes the project lock entry if absent (same guarantee the CLI's
    install_cmd provides, so both call sites get a fully-ready project canonical).

    Raises InstallError if the slug is not in the global library lock.
    """
    from agent_toolkit_cli.skill_lock import (
        LockEntry, add_entry, clone_url_from_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.skill_paths import lock_file_path

    global_lock = read_lock(global_lock_path)
    entry = global_lock.skills.get(slug)
    if entry is None:
        raise InstallError(f"{slug}: not in global library")

    project_canonical = project / ".agents" / "skills" / slug
    if not project_canonical.exists():
        project_canonical.parent.mkdir(parents=True, exist_ok=True)
        source_url = clone_url_from_entry(entry)
        skill_git.clone(source_url, project_canonical, ref=entry.ref, env=env)

    project_lock_path = lock_file_path(scope="project", project=project)
    project_lock = read_lock(project_lock_path)
    if slug not in project_lock.skills:
        proj_entry = LockEntry(
            source=entry.source,
            source_type=entry.source_type,
            ref=entry.ref,
            skill_path=entry.skill_path,
            upstream_sha=None,
            local_sha=None,
        )
        write_lock(project_lock_path, add_entry(project_lock, slug, proj_entry))

    return project_canonical


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
            skill_git.merge(canonical, ref=parsed.ref or "main", env=env)
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
    """Legacy 5-harness shortcut: full remove (every symlink + canonical)."""
    p = plan(
        slug=slug, scope=scope,
        source=None, ref=None,
        target_agents=(),
        home=home, project=project,
    )
    apply(p, home=home, project=project, env=None)
    canonical = canonical_skill_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists():
        shutil.rmtree(canonical)
