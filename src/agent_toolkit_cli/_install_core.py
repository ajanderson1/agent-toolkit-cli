"""Kind-agnostic install engine. Bound by per-kind facades (skill_install,
future agent_install). All public symbols are re-exported from the facades
so existing call sites keep working.

PR1 boundary: any helper that has to know whether the asset is a skill or
an agent (e.g. _universal_bundle_link, _project_universal_link) lives in
the facade, NOT here. The core takes a KindBinding when it needs to know
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
)
from agent_toolkit_cli.skill_source import ParsedSource


class InstallError(RuntimeError):
    """Base error for install failures."""


def _doctor_hint(slug: str, scope: str) -> str:
    """Suggest the doctor command that clears a blocking stray symlink."""
    flag = "-g" if scope == "global" else "-p"
    return f"\n  Run: agent-toolkit-cli skill doctor {flag}  (removes stray symlinks)"


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
      - Global + universal: SKIPPED. ~/.agents/skills/<slug> → library is
        created via the universal bundle path in apply().
      - Project + universal: NOT skipped. Canonical is in the external store;
        each universal agent gets <project>/.agents/skills/<slug> → store.
      - Global + non-universal: NOT skipped (symlink → library).
      - Project + non-universal: NOT skipped. The agent root dir is auto-created
        by apply() via link.parent.mkdir(parents=True, exist_ok=True).

    The special "universal" bundle token is handled in apply() before
    _should_skip_symlink is called; it never reaches here as an agent_name.
    """
    cfg = get_agent(agent_name)
    if cfg.is_universal and scope == "global":
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
    universal_bundle_link: Callable[[str], Path] | None = None,
    synthetic_names: frozenset[str] = frozenset(),
) -> InstallPlan:
    """Compute the minimal add/remove delta to reach target_agents.

    `universal_bundle_link` is injected by the facade — it is the kind-
    specific function that returns the per-slug bundle path (e.g.
    `~/.agents/skills/<slug>` for skills). Defaults to None for callers
    that do not need it (most plan-only computations).

    `synthetic_names` is the set of catalog tokens that are virtual entries
    rather than real harness symlink targets (e.g. the skill facade injects
    `frozenset({"universal", "general-skill"})`). The core treats it as
    opaque — it never names a specific kind's synthetics itself.
    """
    for n in target_agents:
        if n not in AGENTS:
            raise UnknownAgentError(n)
    current = _current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
        universal_bundle_link=universal_bundle_link,
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
    universal_bundle_link: Callable[[str], Path] | None = None,
    synthetic_names: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Return agents whose symlink currently resolves to our canonical.

    Includes the synthetic 'universal' bundle token at global scope when
    `universal_bundle_link(slug)` is a symlink to the library canonical.

    `synthetic_names` enumerates catalog tokens that are virtual entries
    (handled separately from real harness symlinks) and are skipped from
    the per-agent iteration. The core treats the set as opaque: each
    facade injects the synthetics for its own kind (skills inject the
    pair containing the universal bundle token and the general projection
    token; agents will inject their own).
    """
    canonical = canonical_skill_dir(
        slug, scope=scope, home=home, project=project,
    )
    canonical_real = canonical.resolve() if canonical.exists() else canonical

    linked: list[str] = []

    if scope == "global" and universal_bundle_link is not None:
        bundle_link = universal_bundle_link(slug)
        if bundle_link.is_symlink() and bundle_link.resolve() == canonical_real:
            linked.append("universal")

    for name in AGENTS:
        # Skip facade-injected synthetic catalog tokens — they're handled
        # by the facade (e.g. the universal bundle link above), not by the
        # per-agent symlink scan.
        if name in synthetic_names:
            continue

        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            continue

        link = agent_projection_dir(
            name, slug, scope=scope, home=home, project=project,
        )
        if link.is_symlink() and link.resolve() == canonical_real:
            linked.append(name)
    return tuple(linked)
