"""Asset-type-agnostic path/lock-filename core. Bound by per-asset-type facades.

An `AssetTypeBinding` carries everything the path helpers need to know about a
specific asset type. `SKILL_BINDING`, `INSTRUCTIONS_BINDING`, `AGENT_BINDING`,
and `PI_EXTENSION_BINDING` are the four bindings instantiated today (PR1 cut
the seam; the instructions, agent, and pi-extension asset types were added in
their own PRs).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssetTypeBinding:
    asset_type: str            # "skill" | "agent"
    canonical_dirname: str     # "skills" | "agents" — used in the catalog config's per-harness dir
    library_subdir: str        # "skills" | "agents" — directory name under ~/.agent-toolkit/
    lock_filename: str         # "skills-lock.json" | "agents-lock.json"
    standard_harness_name: str  # "standard-skill" | "standard-agent"


SKILL_BINDING = AssetTypeBinding(
    asset_type="skill",
    canonical_dirname="skills",
    library_subdir="skills",
    lock_filename="skills-lock.json",
    standard_harness_name="standard-skill",
)

INSTRUCTIONS_BINDING = AssetTypeBinding(
    asset_type="instructions",
    canonical_dirname="instructions",
    library_subdir="instructions",
    lock_filename="instructions-lock.json",
    standard_harness_name="standard-instructions",
)


AGENT_BINDING = AssetTypeBinding(
    asset_type="agent",
    canonical_dirname="agents",
    library_subdir="agents",
    lock_filename="agents-lock.json",
    standard_harness_name="standard-agent",
)


PI_EXTENSION_BINDING = AssetTypeBinding(
    asset_type="pi-extension",
    canonical_dirname="pi-extensions",
    library_subdir="pi-extensions",
    lock_filename="pi-extensions-lock.json",
    standard_harness_name="standard-pi-extension",
)


def library_root_for_asset_type(
    binding: AssetTypeBinding, env: dict[str, str] | None = None
) -> Path:
    """Return the library root for a given asset type.

    For the skill asset type this preserves the existing
    `$AGENT_TOOLKIT_SKILLS_ROOT` override; for other asset types the env
    override does not apply (intentional — other asset types get their own
    override variable in their own PR if needed).
    Falls back to ~/.agent-toolkit/<binding.library_subdir>/.
    """
    resolved_env = env if env is not None else os.environ
    if binding.asset_type == "skill":
        override = resolved_env.get("AGENT_TOOLKIT_SKILLS_ROOT", "").strip()
        if override:
            return Path(override)
    # Use Path.home() to match the existing skill_paths.library_root() exactly.
    # monkeypatch.setenv("HOME", ...) is honoured because Path.home() reads
    # $HOME from os.environ, which monkeypatch updates.
    return Path.home() / ".agent-toolkit" / binding.library_subdir


def library_lock_path_for_asset_type(
    binding: AssetTypeBinding, env: dict[str, str] | None = None
) -> Path:
    """Return the global lock-file path for a given asset type.

    Lives at <library_root>.parent / <binding.lock_filename>, e.g.
    ~/.agent-toolkit/skills-lock.json by default.
    """
    return library_root_for_asset_type(binding, env).parent / binding.lock_filename
