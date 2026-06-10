"""Agent-flavoured facade over `_install_core.py`.

v3.0.0 PR2 — mirrors `skill_install.py` for the agent (subagent) asset type.
Binds AGENT_BINDING + _AGENT_SYNTHETIC_NAMES into the core. apply()
dispatches to per-mechanism adapters from `agent_adapters/` instead of
the skill facade's uniform-symlink projection.

The agents asset type's standard projection is the `.claude/agents/<slug>.md`
slot (#361) — `standard_bundle_link` stays None because the slot is an
adapter, not a core bundle link. The slot is ONE file with many native
readers; harness tokens whose destination IS that file (claude-code at
both scopes, kode at project scope) are normalized to `standard` in every
facade path (plan targets, the linked scan, apply, uninstall) so scans
never double-report it and no computed delta can delete the shared file.
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
# "standard-agent" mirrors "standard-skill" from the skill facade. "standard"
# is NOT synthetic for the agent asset type (#361): it is the real installable
# .claude/agents/<slug>.md slot, dispatched in agent_adapters.get_adapter()
# ahead of the catalog (whose "standard" entry is the skills pseudo-agent).
_AGENT_SYNTHETIC_NAMES: frozenset[str] = frozenset({"standard-agent"})


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
    scanner. Agents have no standard-bundle concept, so
    standard_bundle_link=None.

    The injected scanner is essential: the core's built-in scan looks for a
    SYMLINK at the SKILL projection path, but agent adapters write REAL FILES
    at agent-specific destinations. Without the override the scan always
    returns () for agents, which (a) makes a full-remove plan empty (uninstall
    orphans every file — the PR #268 bug) and (b) makes every re-install
    spuriously re-add already-installed harnesses.

    Target tokens are normalized to `standard` when their destination IS the
    standard slot (#361): the scan reports the slot as `standard`, so an
    unnormalized covered token (e.g. target=('claude-code',) over an existing
    slot) would compute add=claude-code + remove=standard — a delta that,
    applied, installs then deletes the SAME shared file.
    """
    normalized_target = tuple(dict.fromkeys(
        _normalize_to_standard(n, slug, scope=scope, home=home, project=project)
        for n in target_agents
    ))
    return _core_plan(
        slug=slug, scope=scope, source=source, ref=ref,
        target_agents=normalized_target, home=home, project=project,
        canonical_dir_resolver=canonical_agent_dir,
        standard_bundle_link=None,
        synthetic_names=_AGENT_SYNTHETIC_NAMES,
        current_linked_resolver=_current_linked_agents,
    )


def _current_linked_agents(
    *, slug: str, scope: Scope,
    home: Path | None, project: Path | None,
    canonical_dir_resolver=None,
    standard_bundle_link=None,
    synthetic_names: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Adapter-aware "currently linked" scan for the agent asset type.

    Diverges from the core's symlink-at-skill-path scan: for each supported
    harness (subagent_mechanism != 'none'), ask its adapter where it WOULD
    install (adapter.destination(...)) and test whether that real file
    exists. A harness whose destination exists is "currently linked".

    Synthetic tokens (standard-agent) are skipped. Unsupported harnesses
    (mechanism='none', incl. the 4 PR2-disabled config_file_folder cells)
    raise UnsupportedMechanismError from get_adapter() and are skipped.
    Adapters that fail-loud on a destination they cannot resolve (e.g. dexto
    at project scope) are treated as not-linked rather than crashing the scan.

    Dedupe-by-destination (#361): the standard slot is checked FIRST and
    reported as `standard`; any harness whose destination is the SAME file
    (claude-code at both scopes, kode at project scope) is skipped, or the
    scan would double-report one file and a computed delta could remove the
    shared slot out from under its other readers.

    The kwargs `canonical_dir_resolver`/`standard_bundle_link` are accepted
    only to satisfy the core's `current_linked_resolver` call signature; they
    are irrelevant to the agent asset type and ignored.
    """
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError
    from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std

    linked: list[str] = []
    seen_dests: set[Path] = set()
    try:
        std_dest = _std().destination(
            slug, scope=scope, home=home, project=project,
        )
    except ValueError:
        # Slot unresolvable for these args (e.g. global scope, home=None).
        std_dest = None
    if std_dest is not None:
        seen_dests.add(std_dest)
        if std_dest.exists() or std_dest.is_symlink():
            linked.append("standard")
    for name in _AGENTS:
        if name == "standard":
            # The catalog's "standard" entry is the skills bundle pseudo-
            # agent; the agents asset-type slot was handled above.
            continue
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
        if dest in seen_dests:
            continue
        if dest.exists() or dest.is_symlink():
            linked.append(name)
    return tuple(linked)


def _normalize_to_standard(
    name: str, slug: str, *, scope: Scope,
    home: Path | None, project: Path | None,
) -> str:
    """Return 'standard' when `name`'s destination IS the standard slot
    (claude-code at both scopes; kode at project scope), else `name` (#361).

    Shared by BOTH facade mutation paths (apply's add/remove loops and
    uninstall's direct adapter loop) plus plan()'s target normalization:
    the slot is ONE file with many readers, so a covered token must route
    to the standard adapter (sentinel + ownership guard), never to its own
    per-harness adapter, which would bypass the sentinel contract.
    """
    if name == "standard":
        return name
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError
    from agent_toolkit_cli.agent_adapters.standard import adapter_for as _std

    try:
        std_dest = _std().destination(
            slug, scope=scope, home=home, project=project,
        )
        adapter = agent_adapters.get_adapter(name)
        dest = adapter.destination(slug, scope=scope, home=home, project=project)
        if dest == std_dest:
            return "standard"
    except (ValueError, _UnknownAgentError, UnsupportedMechanismError):
        pass
    return name


def apply(
    plan: InstallPlan,
    *,
    home: Path | None = None,
    project: Path | None = None,
    env: dict[str, str] | None = None,
) -> InstallResult:
    """Execute the agent-install plan.

    For each agent in plan.add_agents:
      - Skip synthetic tokens (standard-agent).
      - Normalize to "standard" when the token's destination IS the standard
        slot (#361); a seen-set skips tokens that normalize to an
        already-processed name.
      - Resolve the mechanism via agent_adapters.get_adapter().
      - If get_adapter() raises UnsupportedMechanismError, record as skipped.
      - Otherwise call adapter.install(slug, canonical_path/<agent_file>, …).

    For each agent in plan.remove_agents:
      - Skip synthetic tokens.
      - Normalize + seen-set dedupe, as above; the standard adapter gets
        canonical_content threaded for its ownership-guarded detach.
      - Call adapter.uninstall(slug, …). Idempotent.

    Plans should come from plan(), which normalizes target tokens BEFORE the
    delta: a hand-built plan whose add_agents and remove_agents both contain
    tokens that normalize to "standard" nets to a DELETE of the shared slot
    (add installs it, the remove loop then unlinks it).
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

    # #361: tokens whose destination IS the standard slot route through the
    # standard adapter (sentinel + ownership guard). A seen-set prevents
    # double-processing when several tokens normalize to the same slot
    # (e.g. claude-code + kode at project scope).
    seen_add: set[str] = set()
    for name in plan.add_agents:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        name = _normalize_to_standard(
            name, plan.slug, scope=plan.scope, home=home, project=project,
        )
        if name in seen_add:
            continue
        seen_add.add(name)
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
    seen_remove: set[str] = set()
    for name in plan.remove_agents:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        name = _normalize_to_standard(
            name, plan.slug, scope=plan.scope, home=home, project=project,
        )
        if name in seen_remove:
            continue
        seen_remove.add(name)
        try:
            adapter = agent_adapters.get_adapter(name)
        except UnsupportedMechanismError:
            continue
        if name == "standard":
            # Ownership-guarded detach: the canonical content authorizes
            # removal of a sentinel-less pre-#361 slot (see adapter docstring).
            adapter.uninstall(
                plan.slug,
                scope=plan.scope, home=home, project=project,
                canonical_content=content_path,
            )
        else:
            adapter.uninstall(
                plan.slug,
                scope=plan.scope, home=home, project=project,
            )

    # Update lock — agent_path identifies which file was written.
    lock_action: Literal["added", "updated", "unchanged"] = "unchanged"
    if plan.source is not None:
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
            skill_git.merge(
                canonical,
                ref=skill_git.resolve_ref(parsed.ref, canonical, env=env),
                env=env,
            )
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

    The agent asset type cannot rely on the core's symlink-at-skill-path scan to
    discover projections: adapters write REAL FILES, so the scan returned ()
    and every projected file was ORPHANED (PR #268). We therefore call each
    requested harness's adapter.uninstall() DIRECTLY, so the real destination
    files are removed regardless of what plan() would compute. `harnesses` is
    the explicit set the caller installed; passing it makes removal independent
    of any scan. Adapters are idempotent (no-op if the destination is already
    gone), so over-listing a harness is harmless.
    """
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError

    # #361: the standard adapter's detach is ownership-guarded — the scope's
    # canonical <slug>.md authorizes removing a sentinel-less pre-#361 slot.
    canonical_content: Path | None
    try:
        canonical_content = canonical_agent_dir(
            slug, scope=scope, home=home, project=project,
        ) / f"{slug}.md"
    except ValueError:
        canonical_content = None

    # Remove every requested projected file via its own adapter (idempotent).
    # The canonical and the lock entry are deliberately left intact — see the
    # docstring (#303). `remove()` owns library deletion.
    # Tokens whose destination IS the standard slot normalize to "standard"
    # (#361) so the .attk sentinel is cleaned up with the file; the seen-set
    # keeps e.g. harnesses=("standard", "claude-code") from double-processing
    # one slot.
    seen: set[str] = set()
    for name in harnesses:
        if name in _AGENT_SYNTHETIC_NAMES:
            continue
        name = _normalize_to_standard(
            name, slug, scope=scope, home=home, project=project,
        )
        if name in seen:
            continue
        seen.add(name)
        try:
            adapter = agent_adapters.get_adapter(name)
        except (UnsupportedMechanismError, _UnknownAgentError):
            continue
        try:
            if name == "standard":
                adapter.uninstall(
                    slug, scope=scope, home=home, project=project,
                    canonical_content=canonical_content,
                )
            else:
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
