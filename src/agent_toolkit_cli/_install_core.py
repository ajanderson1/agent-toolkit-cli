"""Asset-type-agnostic install engine. Bound by per-asset-type facades (skill_install,
future agent_install). All public symbols are re-exported from the facades
so existing call sites keep working.

PR1 boundary: any helper that has to know whether the asset is a skill or
an agent (e.g. _standard_bundle_link, _project_standard_link) lives in
the facade, NOT here. The core takes a AssetTypeBinding when it needs to know
the canonical dirname, lock filename, or general-harness name.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal

from agent_toolkit_cli.skill_agents import (
    AGENTS, UnknownAgentError, get_agent,
)
from agent_toolkit_cli.skill_paths import (
    Scope,
    agent_projection_dir,
    canonical_skill_dir,
    is_skill_projection_available,
)
from agent_toolkit_cli.skill_source import ParsedSource


class InstallError(RuntimeError):
    """Base error for install failures."""


def _doctor_hint(slug: str, scope: str, asset_type_noun: str = "skill") -> str:
    """Suggest the doctor command that clears a blocking stray symlink.

    `asset_type_noun` is the CLI noun for the asset type ("skill" today; "agent"
    once PR4 adds the agent CLI verb group). Defaults to "skill" so existing
    skill-facade callers keep their current error message verbatim.
    """
    flag = "-g" if scope == "global" else "-p"
    return f"\n  Run: agent-toolkit-cli {asset_type_noun} doctor {flag}  (removes stray symlinks)"


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
        raise InstallError(f"{dest}: refusing to overwrite existing path")
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
    skipped: tuple[str, ...]
    lock_action: Literal["added", "updated", "unchanged"]


def _should_skip_symlink(
    *, agent_name: str, scope: Scope, project: Path | None,
) -> tuple[bool, str]:
    """Return (skip?, reason). Mirrors installer.ts:296-323 with v2.2 adjustments.

    v2.2 semantics (post-store relocation):
      - Global + standard (skill-only, no real agent mechanism): SKIPPED.
        ~/.agents/skills/<slug> → library is created via the standard bundle
        path in apply(). These are "pure standard" cells: is_standard=True
        AND subagent_mechanism='none' (e.g. codex, amp, cline).
      - Global + dual-flagged (is_standard=True + real subagent_mechanism):
        NOT skipped. The cell has a real agent adapter that handles install
        independently of the skill-asset-type standard bundle (e.g. cursor has
        subagent_mechanism='symlink'; gemini-cli has 'translate'). PR3 fix.
      - Project + standard: NOT skipped. Canonical is in the external store;
        each standard agent gets <project>/.agents/skills/<slug> → store.
      - Global + non-standard: NOT skipped (symlink → library).
      - Project + non-standard: NOT skipped. The agent root dir is auto-created
        by apply() via link.parent.mkdir(parents=True, exist_ok=True).

    The special "standard" bundle token is handled in apply() before
    _should_skip_symlink is called; it never reaches here as an agent_name.

    PR3 (universal→general rename) made this predicate asset-type-aware: a cell
    that is both skill-standard (skills_dir == ".agents/skills") AND has a
    real agent adapter (subagent_mechanism != "none") must NOT be skipped —
    the agent-asset-type adapter handles the install via get_adapter(), and the
    skill-asset-type standard bundle still covers it for the skills path.
    The agent facade's plan() injects its own adapter-aware scanner and never
    calls this predicate; it is called only in the SKILL-asset-type path via
    _current_linked_agents and skill_install.apply().
    """
    cfg = get_agent(agent_name)
    # Skip only "pure standard" cells: is_standard with no real agent mechanism.
    # Dual-flagged cells (is_standard + real subagent_mechanism) must NOT be
    # skipped — their agent adapter handles the install independently.
    if cfg.is_standard and scope == "global" and cfg.subagent_mechanism == "none":
        return True, "standard-global"
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
    canonical_dir_resolver: Callable[..., Path] | None = None,
    standard_bundle_link: Callable[[str], Path] | None = None,
    synthetic_names: frozenset[str] = frozenset(),
    current_linked_resolver: Callable[..., tuple[str, ...]] | None = None,
) -> InstallPlan:
    """Compute the minimal add/remove delta to reach target_agents.

    `canonical_dir_resolver` is the asset-type-specific resolver returning the
    canonical install directory for a slug at a given scope (e.g.
    `canonical_skill_dir` for skills, `canonical_agent_dir` for agents).
    Required so the core stays asset-type-blind; defaults to canonical_skill_dir
    for backward compatibility with callers that haven't migrated yet.

    `standard_bundle_link` is injected by the facade — it is the asset-type-
    specific function that returns the per-slug bundle path (e.g.
    `~/.agents/skills/<slug>` for skills). Defaults to None for callers
    that do not need it (most plan-only computations).

    `synthetic_names` is the set of catalog tokens that are virtual entries
    rather than real harness symlink targets (e.g. the skill facade injects
    `frozenset({"standard", "standard-skill"})`). The core treats it as
    opaque — it never names a specific asset type's synthetics itself.

    `current_linked_resolver` overrides the built-in `_current_linked_agents`
    scan. The skill facade leaves it None (the symlink-at-projection-path scan
    is correct for skills). The agent facade injects an adapter-aware scanner
    that resolves each harness's REAL destination and tests `dest.exists()` —
    because agent adapters write real files, never symlinks at the skill path,
    so the built-in scan always returns () for the agent asset type (the PR #268 bug).
    Called with the same keyword args as `_current_linked_agents`.
    """
    for n in target_agents:
        if n not in AGENTS:
            raise UnknownAgentError(n)
    scanner = current_linked_resolver if current_linked_resolver is not None else _current_linked_agents
    current = scanner(
        slug=slug, scope=scope, home=home, project=project,
        canonical_dir_resolver=canonical_dir_resolver,
        standard_bundle_link=standard_bundle_link,
        synthetic_names=synthetic_names,
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
    canonical_dir_resolver: Callable[..., Path] | None = None,
    standard_bundle_link: Callable[[str], Path] | None = None,
    synthetic_names: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Return agents whose symlink currently resolves to our canonical.

    `canonical_dir_resolver` is the asset-type-specific canonical resolver
    (e.g. `canonical_skill_dir`, `canonical_agent_dir`). Required so the
    scan compares against the correct canonical path for the asset type;
    defaults to `canonical_skill_dir` for backward compatibility.

    Includes the synthetic 'standard' bundle token at global scope when
    `standard_bundle_link(slug)` is a symlink to the library canonical.

    `synthetic_names` enumerates catalog tokens that are virtual entries
    (handled separately from real harness symlinks) and are skipped from
    the per-agent iteration. The core treats the set as opaque: each
    facade injects the synthetics for its own asset type (skills inject the
    pair containing the standard bundle token and the standard projection
    token; agents inject their own).
    """
    resolver = canonical_dir_resolver if canonical_dir_resolver is not None else canonical_skill_dir
    canonical = resolver(
        slug, scope=scope, home=home, project=project,
    )
    canonical_real = canonical.resolve() if canonical.exists() else canonical

    linked: list[str] = []

    if scope == "global" and standard_bundle_link is not None:
        bundle_link = standard_bundle_link(slug)
        if bundle_link.is_symlink() and bundle_link.resolve() == canonical_real:
            linked.append("standard")

    for name in AGENTS:
        # Skip facade-injected synthetic catalog tokens — they're handled
        # by the facade (e.g. the standard bundle link above), not by the
        # per-agent symlink scan.
        if name in synthetic_names:
            continue

        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            continue

        # Catalog-wide scan: a context-unavailable Paperplip (global scope, or
        # outside a company project) has no projection destination to probe, so
        # skip it rather than letting agent_projection_dir() raise. Explicit
        # Paperclip targets still go through validate_projection_context().
        if not is_skill_projection_available(name, scope=scope, project=project):
            continue

        link = agent_projection_dir(
            name, slug, scope=scope, home=home, project=project,
        )
        if link.is_symlink() and link.resolve() == canonical_real:
            linked.append(name)
    return tuple(linked)
