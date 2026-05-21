"""Data model for the TUI's skill tab.

Reads the lock + filesystem to produce SkillRow records with per-(agent, scope)
cell state plus a working-tree state badge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_cli.skill_install import _should_skip_symlink
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import (
    agent_projection_dir, canonical_skill_dir, lock_file_path,
)

State = Literal["clean", "dirty", "missing", "copy"]
Scope = Literal["global", "project"]

# Agents whose cells the TUI grid renders interactively. Mirrors v2.0.0's
# 5-harness shortcut for the interactive surface; the long tail of agents
# stays CLI-only.
INTERACTIVE_AGENTS: tuple[str, ...] = ("claude-code", "pi")


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


def _cell_for(
    slug: str, agent_name: str, *,
    scope: Scope, home: Path | None, project: Path | None,
) -> SkillCell:
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
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
    rows: list[SkillRow] = []
    for slug in sorted(lock.skills):
        entry = lock.skills[slug]
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project,
        )
        if not canonical.exists():
            state: State = "missing"
        elif not skill_git.is_git_repo(canonical):
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
        ))
    return rows
