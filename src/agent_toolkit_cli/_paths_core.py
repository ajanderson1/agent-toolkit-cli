"""Kind-agnostic path/lock-filename core. Bound by per-kind facades.

A `KindBinding` carries everything the path helpers need to know about a
specific asset kind. `SKILL_BINDING`, `INSTRUCTIONS_BINDING`, `AGENT_BINDING`,
and `PI_EXTENSION_BINDING` are the four bindings instantiated today (PR1 cut
the seam; the instructions, agent, and pi-extension kinds were added in their
own PRs).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KindBinding:
    kind: str                  # "skill" | "agent"
    canonical_dirname: str     # "skills" | "agents" — used in the catalog config's per-harness dir
    library_subdir: str        # "skills" | "agents" — directory name under ~/.agent-toolkit/
    lock_filename: str         # "skills-lock.json" | "agents-lock.json"
    general_harness_name: str  # "standard-skill" | "standard-agent"


SKILL_BINDING = KindBinding(
    kind="skill",
    canonical_dirname="skills",
    library_subdir="skills",
    lock_filename="skills-lock.json",
    general_harness_name="standard-skill",
)

INSTRUCTIONS_BINDING = KindBinding(
    kind="instructions",
    canonical_dirname="instructions",
    library_subdir="instructions",
    lock_filename="instructions-lock.json",
    general_harness_name="general-instructions",
)


AGENT_BINDING = KindBinding(
    kind="agent",
    canonical_dirname="agents",
    library_subdir="agents",
    lock_filename="agents-lock.json",
    general_harness_name="standard-agent",
)


PI_EXTENSION_BINDING = KindBinding(
    kind="pi-extension",
    canonical_dirname="pi-extensions",
    library_subdir="pi-extensions",
    lock_filename="pi-extensions-lock.json",
    general_harness_name="general-pi-extension",
)


def library_root_for_kind(binding: KindBinding, env: dict[str, str] | None = None) -> Path:
    """Return the library root for a given kind.

    For the skill kind this preserves the existing `$AGENT_TOOLKIT_SKILLS_ROOT`
    override; for other kinds the env override does not apply (intentional —
    other kinds get their own override variable in their own PR if needed).
    Falls back to ~/.agent-toolkit/<binding.library_subdir>/.
    """
    resolved_env = env if env is not None else os.environ
    if binding.kind == "skill":
        override = resolved_env.get("AGENT_TOOLKIT_SKILLS_ROOT", "").strip()
        if override:
            return Path(override)
    # Use Path.home() to match the existing skill_paths.library_root() exactly.
    # monkeypatch.setenv("HOME", ...) is honoured because Path.home() reads
    # $HOME from os.environ, which monkeypatch updates.
    return Path.home() / ".agent-toolkit" / binding.library_subdir


def library_lock_path_for_kind(binding: KindBinding, env: dict[str, str] | None = None) -> Path:
    """Return the global lock-file path for a given kind.

    Lives at <library_root>.parent / <binding.lock_filename>, e.g.
    ~/.agent-toolkit/skills-lock.json by default.
    """
    return library_root_for_kind(binding, env).parent / binding.lock_filename
