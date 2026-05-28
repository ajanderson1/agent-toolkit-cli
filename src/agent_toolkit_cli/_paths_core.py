"""Kind-agnostic path/lock-filename core. Bound by per-kind facades.

A `KindBinding` carries everything the path helpers need to know about a
specific asset kind. `SKILL_BINDING` is the only binding PR1 instantiates;
`AGENT_BINDING` arrives in PR2.
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
    general_harness_name: str  # "general-skill" | "general-agent"


SKILL_BINDING = KindBinding(
    kind="skill",
    canonical_dirname="skills",
    library_subdir="skills",
    lock_filename="skills-lock.json",
    general_harness_name="general-skill",
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
    # Resolve $HOME from the supplied env so tests are not coupled to the
    # process-wide os.environ when they monkeypatch HOME.
    home = Path(resolved_env.get("HOME") or str(Path.home()))
    return home / ".agent-toolkit" / binding.library_subdir


def library_lock_path_for_kind(binding: KindBinding, env: dict[str, str] | None = None) -> Path:
    """Return the global lock-file path for a given kind.

    Lives at <library_root>.parent / <binding.lock_filename>, e.g.
    ~/.agent-toolkit/skills-lock.json by default.
    """
    return library_root_for_kind(binding, env).parent / binding.lock_filename
