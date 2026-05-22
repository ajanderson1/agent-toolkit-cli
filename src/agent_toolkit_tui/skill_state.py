"""Data model for the TUI's skill tab.

Reads the lock + filesystem to produce SkillRow records with per-(agent, scope)
cell state plus a working-tree state badge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_cli.skill_install import _should_skip_symlink
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import (
    agent_projection_dir, canonical_skill_dir, library_lock_path,
    parent_clone_path,
)

# "library" means the skill exists in the library but is not installed in this
# project (no project canonical at <project>/.agents/skills/<slug>/). This is
# the normal pre-install state and is rendered in dim/gray — not alarming.
State = Literal["clean", "dirty", "missing", "copy", "library"]
Scope = Literal["global", "project"]

# Agents whose cells the TUI grid renders interactively. Mirrors v2.0.0's
# 5-harness shortcut for the interactive surface; the long tail of agents
# stays CLI-only.
# "universal" is first — it represents the bundle toggle (~/.agents/skills/<slug>
# symlink at global scope; project canonical existence at project scope).
INTERACTIVE_AGENTS: tuple[str, ...] = ("universal", "claude-code", "pi")


@dataclass(frozen=True)
class SkillCell:
    linked: bool       # symlink resolves to canonical (or canonical exists for skipped)
    drift: bool        # symlink exists but points elsewhere
    skipped: bool      # universal-global: no symlink needed, canonical IS the dir


@dataclass
class SkillRow:
    slug: str
    source: str
    ref: str
    state: State
    cells: dict[tuple[str, str], SkillCell] = field(default_factory=dict)
    description: str = ""


def _read_skill_description(canonical: Path) -> str:
    """Best-effort: read the `description:` from <canonical>/SKILL.md frontmatter.

    Returns "" for any failure mode (missing dir, missing file, no frontmatter,
    parse error, non-dict, missing key). Collapses whitespace so the cell stays
    single-line.
    """
    if not canonical.exists() or not canonical.is_dir():
        return ""
    skill_md = canonical / "SKILL.md"
    try:
        text = skill_md.read_text()
    except OSError:
        return ""
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    if end == -1:
        return ""
    try:
        fm = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return ""
    if not isinstance(fm, dict):
        return ""
    raw = fm.get("description")
    if raw is None:
        return ""
    return " ".join(str(raw).split())


def _universal_bundle_link(slug: str) -> Path:
    """Return the ~/.agents/skills/<slug> path for the universal-bundle install."""
    return Path.home() / ".agents" / "skills" / slug


def _cell_for(
    slug: str, agent_name: str, *,
    scope: Scope, home: Path | None, project: Path | None,
) -> SkillCell:
    # The synthetic "universal" token has its own detection logic: it does NOT
    # use _should_skip_symlink (that function doesn't understand "universal" as
    # an agent_name — the engine strips it before calling skip checks).
    if agent_name == "universal":
        if scope == "global":
            # Global: linked iff ~/.agents/skills/<slug> is a symlink that
            # resolves to the library canonical.
            canonical = canonical_skill_dir(
                slug, scope=scope, home=home, project=project,
            )
            bundle_link = _universal_bundle_link(slug)
            if not bundle_link.is_symlink():
                return SkillCell(linked=False, drift=False, skipped=False)
            canonical_real = canonical.resolve() if canonical.exists() else canonical
            if bundle_link.resolve() == canonical_real:
                return SkillCell(linked=True, drift=False, skipped=False)
            # Symlink exists but points elsewhere — drifted.
            return SkillCell(linked=False, drift=True, skipped=False)
        else:
            # Project scope: linked iff <project>/.agents/skills/<slug>/ exists
            # as a directory (not a symlink — it's the project canonical).
            canonical = canonical_skill_dir(
                slug, scope=scope, home=home, project=project,
            )
            linked = canonical.exists() and canonical.is_dir() and not canonical.is_symlink()
            return SkillCell(linked=linked, drift=False, skipped=False)

    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    skip, _ = _should_skip_symlink(
        agent_name=agent_name, scope=scope, project=project,
    )
    if skip:
        return SkillCell(linked=canonical.exists(), drift=False, skipped=True)
    link = agent_projection_dir(
        agent_name, slug, scope=scope, home=home, project=project,
    )
    if not link.is_symlink():
        return SkillCell(linked=False, drift=False, skipped=False)
    canonical_real = canonical.resolve() if canonical.exists() else canonical
    if link.resolve() == canonical_real:
        return SkillCell(linked=True, drift=False, skipped=False)
    return SkillCell(linked=False, drift=True, skipped=False)


def build_skill_rows(
    *, scope: Scope, home: Path | None, project: Path | None,
) -> list[SkillRow]:
    # The library lock is the universe of slugs available on this machine.
    # At global scope the library lock IS the scope lock, so this is equivalent
    # to the previous behaviour. At project scope we read the library lock for
    # row inclusion, then derive per-row state from the project's filesystem.
    lib_lock = read_lock(library_lock_path())
    rows: list[SkillRow] = []
    for slug in sorted(lib_lock.skills):
        entry = lib_lock.skills[slug]
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project,
        )
        if not canonical.exists():
            # Project scope: slug is in the library but not yet installed here.
            # Global scope: library entry recorded but directory was deleted.
            state: State = "library" if scope == "project" else "missing"
        elif entry.parent_url is not None:
            # Monorepo skill — state lives in the parent clone, not the
            # symlinked subpath (which has no `.git/` of its own).
            owner, repo = entry.source.split("/", 1)
            parent_dir = parent_clone_path(
                owner, repo, ref=entry.ref, env=None,
            )
            if not skill_git.is_git_repo(parent_dir):
                # Parent clone missing — user `rm -rf`'d it, or
                # materialised: copy with no parent available.
                state = "copy"
            else:
                wt = skill_git.status(parent_dir, env=None)
                state = (
                    "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                    else "clean"
                )
        elif not skill_git.is_git_repo(canonical):
            # Plain-file install (e.g. `npx skills add --copy`).
            state = "copy"
        else:
            wt = skill_git.status(canonical, env=None)
            state = (
                "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                else "clean"
            )
        cells: dict[tuple[str, str], SkillCell] = {}
        for agent in INTERACTIVE_AGENTS:
            cells[(agent, scope)] = _cell_for(
                slug, agent, scope=scope, home=home, project=project,
            )
        rows.append(SkillRow(
            slug=slug, source=entry.source, ref=entry.ref or "main",
            state=state, cells=cells,
            description=_read_skill_description(canonical),
        ))
    return rows
