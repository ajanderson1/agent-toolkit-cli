"""Data model for the TUI's skill tab.

Reads `.skill-lock.json` (or `skills-lock.json`) and queries `git status`
on each canonical clone to produce SkillRow records.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, lock_file_path

State = Literal["clean", "dirty", "missing", "copy"]


@dataclass(frozen=True)
class SkillRow:
    slug: str
    source: str
    ref: str
    state: State


def build_skill_rows(
    *, scope, home: Path | None, project: Path | None,
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
            # Skills installed by `npx skills add --copy` are plain files
            # with no .git/. We can't run `git status` against them, but
            # they're still on disk and usable by harnesses.
            state = "copy"
        else:
            wt = skill_git.status(canonical, env=None)
            state = (
                "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
            )
        rows.append(SkillRow(
            slug=slug, source=entry.source, ref=entry.ref or "main", state=state,
        ))
    return rows
