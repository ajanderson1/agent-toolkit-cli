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
    plan as _core_plan,
)
from agent_toolkit_cli.agent_paths import (
    Scope,
    canonical_agent_dir,
    lock_file_path,
)
from agent_toolkit_cli.skill_agents import (
    AGENTS as _AGENTS,
    UnknownAgentError as _UnknownAgentError,
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
    synthetic-name set AND injects an adapter-aware "currently linked"
    scanner. Agents have no universal-bundle concept, so
    universal_bundle_link=None.

    The injected scanner is essential: the core's built-in scan looks for a
    SYMLINK at the SKILL projection path, but agent adapters write REAL FILES
    at agent-specific destinations. Without the override the scan always
    returns () for agents, which (a) makes a full-remove plan empty (uninstall
    orphans every file — the PR #268 bug) and (b) makes every re-install
    spuriously re-add already-installed harnesses.
    """
    return _core_plan(
        slug=slug, scope=scope, source=source, ref=ref,
        target_agents=target_agents, home=home, project=project,
        canonical_dir_resolver=canonical_agent_dir,
        universal_bundle_link=None,
        synthetic_names=_AGENT_SYNTHETIC_NAMES,
        current_linked_resolver=_current_linked_agents,
    )


def _current_linked_agents(
    *, slug: str, scope: Scope,
    home: Path | None, project: Path | None,
    canonical_dir_resolver=None,
    universal_bundle_link=None,
    synthetic_names: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Adapter-aware "currently linked" scan for the agent kind.

    Diverges from the core's symlink-at-skill-path scan: for each supported
    harness (subagent_mechanism != 'none'), ask its adapter where it WOULD
    install (adapter.destination(...)) and test whether that real file
    exists. A harness whose destination exists is "currently linked".

    Synthetic tokens (general-agent) are skipped. Unsupported harnesses
    (mechanism='none', incl. the 4 PR2-disabled config_file_folder cells)
    raise UnsupportedMechanismError from get_adapter() and are skipped.
    Adapters that fail-loud on a destination they cannot resolve (e.g. dexto
    at project scope) are treated as not-linked rather than crashing the scan.

    The kwargs `canonical_dir_resolver`/`universal_bundle_link` are accepted
    only to satisfy the core's `current_linked_resolver` call signature; they
    are irrelevant to the agent kind and ignored.
    """
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError

    linked: list[str] = []
    for name in _AGENTS:
        if name in synthetic_names or name in _AGENT_SYNTHETIC_NAMES:
            continue
        try:
            adapter = agent_adapters.get_adapter(name)
        except UnsupportedMechanismError:
            continue
        try:
            dest = adapter.destination(
                slug, scope=scope, home=home, project=project,
            )
        except (ValueError, _UnknownAgentError):
            # Adapter can't resolve a destination for this scope/args (e.g.
            # dexto project scope) — it cannot be linked here. Skip.
            continue
        if dest.exists() or dest.is_symlink():
            linked.append(name)
    return tuple(linked)


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

    # Tool-ownership signal: a lock entry for this slug means agent-toolkit-cli
    # already installed it, so re-writing our own destination files is an
    # allowed refresh (overwrite=True). A fresh install (no lock entry) refuses
    # to clobber a pre-existing foreign file at any destination.
    overwrite = existing_entry is not None

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
            overwrite=overwrite,
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
    """Detach — remove the requested harnesses' projection files only.

    NON-DESTRUCTIVE (issue #303): keeps the library canonical AND the lock
    entry at BOTH scopes, mirroring `skill uninstall` ("Library/project
    canonical untouched") and the CLI command's own contract ("Keeps the
    canonical library entry. Use `agent remove` to fully drop from the
    library."). The destructive path lives in `remove()`.

    The agent kind cannot rely on the core's symlink-at-skill-path scan to
    discover projections: adapters write REAL FILES, so the scan returned ()
    and every projected file was ORPHANED (PR #268). We therefore call each
    requested harness's adapter.uninstall() DIRECTLY, so the real destination
    files are removed regardless of what plan() would compute. `harnesses` is
    the explicit set the caller installed; passing it makes removal independent
    of any scan. Adapters are idempotent (no-op if the destination is already
    gone), so over-listing a harness is harmless.
    """
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError

    # Remove every requested projected file via its own adapter (idempotent).
    # The canonical and the lock entry are deliberately left intact — see the
    # docstring (#303). `remove()` owns library deletion.
    for name in harnesses:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        try:
            adapter = agent_adapters.get_adapter(name)
        except (UnsupportedMechanismError, _UnknownAgentError):
            continue
        try:
            adapter.uninstall(slug, scope=scope, home=home, project=project)
        except ValueError:
            # Adapter can't resolve a destination for these args (e.g. a
            # {HOME}-template harness called with home=None, or dexto at
            # project scope). There is nothing to remove there — treat as a
            # no-op rather than crashing the uninstall.
            continue


def remove(
    *,
    slug: str,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    harnesses: tuple[str, ...],
) -> None:
    """Full removal — projections + lock entry + canonical (global scope).

    The destructive counterpart to `uninstall()` (issue #303). Called by
    `agent remove`. Steps:

      1. Detach all requested harness projections via `uninstall()` (idempotent).
      2. Drop the lock entry at BOTH scopes (the global library lock no longer
         claims a slug we are deleting).
      3. Global scope: rmtree the canonical library entry. Project scope
         preserves the external canonical (dirty-work survives; doctor's orphan
         sweep reclaims it) — matching `skill remove`'s project posture.
    """
    from agent_toolkit_cli.agent_lock import (
        read_lock, remove_entry, write_lock,
    )

    # 1. Remove every projected file (idempotent, non-destructive to library).
    uninstall(
        slug=slug, scope=scope, home=home, project=project, harnesses=harnesses,
    )

    # 2. Drop the lock entry (both scopes).
    lock_path = lock_file_path(scope=scope, home=home, project=project)
    lock = read_lock(lock_path)
    if slug in lock.skills:
        write_lock(lock_path, remove_entry(lock, slug))

    if scope == "project":
        # External canonical preserved (dirty-work survival); doctor reclaims it.
        return

    # 3. Global scope: drop the canonical library entry.
    canonical = canonical_agent_dir(
        slug, scope=scope, home=home, project=project,
    )
    if canonical.exists():
        shutil.rmtree(canonical)
