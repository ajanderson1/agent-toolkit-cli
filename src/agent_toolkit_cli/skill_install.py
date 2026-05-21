"""Canonical-clone + per-agent symlink projection, catalog-aware.

Layout matches vercel-labs/skills:
  canonical: <root>/.agents/skills/<slug>/   (a real git clone)
  symlinks:  <agent.skills_dir>/<slug>       -> canonical

Install rules (mirroring installer.ts:280-323):
  - Global + universal agent  → no per-agent symlink (canonical IS the dir)
  - Global + non-universal    → ~/.<agent.skills_dir>/<slug> symlink
  - Project + universal       → <project>/.agents/skills/<slug> symlink
  - Project + non-universal   → <project>/<agent.skills_dir>/<slug> symlink
                                ONLY IF agent's root dir exists in project
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
    lock_file_path,
)
from agent_toolkit_cli.skill_source import ParsedSource


class InstallError(RuntimeError):
    """Base error for install failures."""


class LockMismatchError(InstallError):
    """Canonical exists on disk but lock entry source differs from request."""


class DirtyCanonicalError(InstallError):
    """Full-remove requested against dirty canonical without --force."""


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
    """Return (skip?, reason). Mirrors installer.ts:296-323."""
    cfg = get_agent(agent_name)
    # Rule 1: universal — canonical IS the agent projection (same path).
    # Applies to both global and project scope because cfg.skills_dir ==
    # ".agents/skills" for universal agents, which equals the canonical dir.
    if cfg.is_universal:
        return True, "universal-global" if scope == "global" else "universal-project"
    # Rule 2: project + non-universal — only symlink if agent root exists.
    if scope == "project":
        project_dir = project or Path.cwd()
        agent_root_name = cfg.skills_dir.split("/")[0]
        if not (project_dir / agent_root_name).exists():
            return True, "agent-root-absent"
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

    For agents where _should_skip_symlink() returns True, 'currently linked'
    is determined by canonical existence (since no symlink is ever created)."""
    canonical = canonical_skill_dir(
        slug, scope=scope, home=home, project=project,
    )
    canonical_real = canonical.resolve() if canonical.exists() else canonical
    canonical_exists = canonical.exists()

    linked: list[str] = []
    for name in AGENTS:
        # Skip the synthetic 'universal' entry — never linked individually.
        if not AGENTS[name].show_in_universal_list and name == "universal":
            continue

        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            # For skipped agents, 'linked' means 'canonical exists'.
            if canonical_exists:
                linked.append(name)
            continue

        link = agent_projection_dir(
            name, slug, scope=scope, home=home, project=project,
        )
        if link.is_symlink() and link.resolve() == canonical_real:
            linked.append(name)
    return tuple(linked)


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
