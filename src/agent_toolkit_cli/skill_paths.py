"""Pure path-computation helpers for the skill lock-file model.

Canonical layout mirrors vercel-labs/skills:
  global:  ~/.agents/skills/<slug>/   +  ~/.agents/.skill-lock.json
  project: <proj>/.agents/skills/<slug>/  +  <proj>/skills-lock.json

Per-harness projections live under ~/.<harness>/skills/<slug> (global) or
<proj>/.<harness>/skills/<slug> (project) as symlinks to the canonical.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

Scope = Literal["project", "global"]

SUPPORTED_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "gemini", "pi")

# Per-harness directory under ~/.<dir>/skills/<slug>; matches our existing
# harness adapters, not vercel-labs/skills' more elaborate mapping.
_HARNESS_DIR = {
    "claude":   ".claude",
    "codex":    ".codex",
    "opencode": ".config/opencode",
    "gemini":   ".gemini",
    "pi":       ".pi",
}


def _root(scope: Scope, home: Path | None, project: Path | None) -> Path:
    if scope == "global":
        if home is None:
            raise ValueError("global scope requires home")
        return home
    if project is None:
        raise ValueError("project scope requires project")
    return project


def canonical_skill_dir(
    slug: str, *, scope: Scope, home: Path | None, project: Path | None
) -> Path:
    return _root(scope, home, project) / ".agents" / "skills" / slug


def lock_file_path(
    *, scope: Scope, home: Path | None, project: Path | None
) -> Path:
    root = _root(scope, home, project)
    if scope == "global":
        return root / ".agents" / ".skill-lock.json"
    return root / "skills-lock.json"


def harness_projection_dir(
    harness: str,
    slug: str,
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> Path:
    if harness not in SUPPORTED_HARNESSES:
        raise ValueError(f"unknown harness: {harness}")
    return _root(scope, home, project) / _HARNESS_DIR[harness] / "skills" / slug
