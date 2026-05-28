"""Kind-agnostic path/lock-filename core. Bound by per-kind facades.

A `KindBinding` carries everything the path helpers need to know about a
specific asset kind. `SKILL_BINDING` is the only binding PR1 instantiates;
`AGENT_BINDING` arrives in PR2.
"""
from __future__ import annotations

from dataclasses import dataclass


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
