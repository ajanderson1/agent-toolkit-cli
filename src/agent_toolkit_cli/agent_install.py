"""Agent-flavoured facade over `_install_core.py`.

v3.0.0 PR2 — mirrors `skill_install.py` for the agent (subagent) kind.
Binds AGENT_BINDING + _AGENT_SYNTHETIC_NAMES into the core. apply()
dispatches to per-mechanism adapters from `agent_adapters/` instead of
the skill facade's uniform-symlink projection.

No universal-bundle concept exists for agents (per spec: agents
don't bundle into a megaprompt), so the facade injects
universal_bundle_link=None.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Literal

from agent_toolkit_cli import agent_adapters, skill_git
from agent_toolkit_cli._install_core import (
    DirtyCanonicalError,  # noqa: F401  re-exported
    InstallError,  # noqa: F401  re-exported
    InstallPlan,  # noqa: F401  re-exported
    InstallResult,
    LockMismatchError,
    _current_linked_agents as _core_current_linked_agents,
    plan as _core_plan,
)
from agent_toolkit_cli.agent_paths import (
    Scope,
    canonical_agent_dir,
    lock_file_path,
)
from agent_toolkit_cli.skill_agents import (
    AGENTS,
    UnknownAgentError,
)
from agent_toolkit_cli.skill_source import ParsedSource

# Catalog tokens that are virtual entries, not real harness install targets.
# Note: no "universal" — that's skill-only. "general-agent" mirrors
# "general-skill" from the skill facade.
_AGENT_SYNTHETIC_NAMES: frozenset[str] = frozenset({"general-agent"})


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

    Thin facade over `_install_core.plan` that binds the agent-specific
    synthetic-name set. Agents have no universal-bundle concept, so
    universal_bundle_link=None.
    """
    return _core_plan(
        slug=slug, scope=scope, source=source, ref=ref,
        target_agents=target_agents, home=home, project=project,
        canonical_dir_resolver=canonical_agent_dir,
        universal_bundle_link=None,
        synthetic_names=_AGENT_SYNTHETIC_NAMES,
    )


def _current_linked_agents(
    *, slug: str, scope: Scope,
    home: Path | None, project: Path | None,
) -> tuple[str, ...]:
    """Mirror of skill_install._current_linked_agents binding the agent
    synthetics AND the agent canonical resolver — so the projection scan
    compares against ~/.agent-toolkit/agents/<slug>/, not the skill canonical."""
    return _core_current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
        canonical_dir_resolver=canonical_agent_dir,
        universal_bundle_link=None,
        synthetic_names=_AGENT_SYNTHETIC_NAMES,
    )


def apply(
    plan: InstallPlan,
    *,
    home: Path | None = None,
    project: Path | None = None,
    env: dict[str, str] | None = None,
) -> InstallResult:
    """Execute the agent-install plan.

    For each agent in plan.add_agents:
      - Skip synthetic tokens (general-agent).
      - Resolve the mechanism via agent_adapters.get_adapter().
      - If get_adapter() raises UnsupportedMechanismError, record as skipped.
      - Otherwise call adapter.install(slug, canonical_path/<agent_file>, …).

    For each agent in plan.remove_agents:
      - Skip synthetic tokens.
      - Call adapter.uninstall(slug, …). Idempotent.
    """
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )

    canonical = canonical_agent_dir(
        plan.slug, scope=plan.scope, home=home, project=project,
    )
    lock_path = lock_file_path(scope=plan.scope, home=home, project=project)
    lock = read_lock(lock_path)
    existing_entry = lock.skills.get(plan.slug)

    # Clone canonical if needed (same pattern as skill_install.apply).
    if plan.source is not None and not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(plan.source.url, canonical, ref=plan.ref, env=env)
    elif plan.source is not None and existing_entry is not None:
        requested = plan.source.owner_repo or plan.source.url
        if existing_entry.source != requested:
            raise LockMismatchError(
                f"{plan.slug}: canonical exists with source "
                f"{existing_entry.source!r}; refusing to overwrite with "
                f"{requested!r}. Run `agent remove {plan.slug}` first."
            )

    # The agent content file inside the canonical. Convention: <slug>.md.
    # Real adapters may override (e.g. devin → AGENT.md, kiro-cli → <slug>.json).
    # The adapter receives the canonical content file as input; it decides
    # the on-disk shape at the destination.
    content_path = canonical / f"{plan.slug}.md"

    created: list[Path] = []
    skipped: list[str] = []

    for name in plan.add_agents:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        try:
            adapter = agent_adapters.get_adapter(name)
        except UnsupportedMechanismError:
            skipped.append(name)
            continue
        out = adapter.install(
            plan.slug, content_path,
            scope=plan.scope, home=home, project=project,
        )
        created.append(out)

    removed: list[Path] = []
    for name in plan.remove_agents:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        try:
            adapter = agent_adapters.get_adapter(name)
        except UnsupportedMechanismError:
            continue
        adapter.uninstall(
            plan.slug,
            scope=plan.scope, home=home, project=project,
        )

    # Update lock — agent_path identifies which file was written.
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
            agent_path=f"{plan.slug}.md",
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
    """Plan + apply convenience wrapper, mirroring skill_install.install()."""
    canonical = canonical_agent_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists() and skill_git.is_git_repo(canonical):
        skill_git.fetch(canonical, env=env)
        try:
            skill_git.merge(canonical, ref=parsed.ref or "main", env=env)
        except skill_git.GitError:
            pass

    p = plan(
        slug=slug, scope=scope,
        source=parsed, ref=parsed.ref,
        target_agents=harnesses,
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
    """Full removal — every projection + canonical tree."""
    p = plan(
        slug=slug, scope=scope,
        source=None, ref=None,
        target_agents=(),
        home=home, project=project,
    )
    apply(p, home=home, project=project, env=None)

    if scope == "project":
        from agent_toolkit_cli.agent_lock import (
            read_lock, remove_entry, write_lock,
        )
        lock_path = lock_file_path(scope="project", project=project)
        lock = read_lock(lock_path)
        if slug in lock.skills:
            write_lock(lock_path, remove_entry(lock, slug))
        return

    canonical = canonical_agent_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists():
        shutil.rmtree(canonical)
