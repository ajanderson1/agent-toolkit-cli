"""Instructions-flavoured facade over `_paths_core.py`.

v3.0.0 — mirrors `skill_paths.py` and `agent_paths.py` for the instructions
(AGENTS.md pointer-symlink) asset type.

Differences from skill/agent paths:
- **No `canonical_<asset_type>_dir`** — instructions has no per-slug subdir. The
  asset is a single file (`AGENTS.md`); pointers live next to it.
- **`global_canonical_agents_md()` / `project_canonical_agents_md()`** — the
  asset's resolved location at each scope. These are what pointers symlink TO.
- **No `project_store_root` / parent-clone helpers** — there is no upstream
  repo to clone.

Public symbols:
    library_root, library_lock_path, project_lock_path,
    global_canonical_agents_md, project_canonical_agents_md,
    lock_file_path
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    INSTRUCTIONS_BINDING,
    library_root_for_asset_type,
)

Scope = Literal["global", "project"]


def library_root() -> Path:
    """Library root: ~/.agent-toolkit/instructions/.

    Reserved for future use (e.g. canonical-content backups). Phase B does not
    write here — the canonical lives at the parent (~/.agent-toolkit/AGENTS.md).
    """
    return library_root_for_asset_type(INSTRUCTIONS_BINDING)


def library_lock_path() -> Path:
    """Global lock at ~/.agent-toolkit/instructions-lock.json.

    Routes through this module's `library_root()` (rather than the shared
    `library_lock_path_for_asset_type` helper) so that tests monkeypatching
    `instructions_paths.library_root` isolate the lock too — mirroring
    `global_canonical_agents_md()` below. Byte-identical on a real machine:
    both resolve to ~/.agent-toolkit/instructions-lock.json.
    """
    return library_root().parent / INSTRUCTIONS_BINDING.lock_filename


def project_lock_path(project_root: Path) -> Path:
    """Project lock at <project_root>/instructions-lock.json."""
    return project_root / "instructions-lock.json"


def global_canonical_agents_md() -> Path:
    """The canonical global AGENTS.md: ~/.agent-toolkit/AGENTS.md.

    This is what global-scope pointers (e.g. ~/.claude/CLAUDE.md) symlink to.
    The toolkit never creates this file — the user authors it. install()
    refuses if it does not exist.
    """
    return library_root().parent / "AGENTS.md"


def project_canonical_agents_md(project_root: Path) -> Path:
    """The canonical project AGENTS.md: <project_root>/AGENTS.md.

    Pointers (e.g. <project_root>/CLAUDE.md) symlink to this file. install()
    refuses if it does not exist.
    """
    return project_root / "AGENTS.md"


def lock_file_path(scope: Scope, project_root: Path | None) -> Path:
    """Dispatch to global or project lock by scope. Matches skill_paths shape."""
    if scope == "global":
        return library_lock_path()
    if scope == "project":
        if project_root is None:
            raise ValueError("project scope requires project_root")
        return project_lock_path(project_root)
    raise ValueError(f"unknown scope: {scope!r}")
