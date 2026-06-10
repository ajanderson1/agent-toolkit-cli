"""Agent-asset-type projection adapters, dispatched by AgentConfig.subagent_mechanism.

PR2 ships three mechanism modules:
  - symlink: 15 harnesses; write a single .md to the harness's agents dir.
  - translate: 10 harnesses; reshape frontmatter or non-md format (toml/json).
  - config_file_folder: 3 harnesses; write definition + mutate registry.

Per-cell quirks (path-template, required frontmatter, format) live in
per-cell dicts INSIDE the mechanism module. Mechanism = code path; cell = data row.

Architecture note — #252 "generalize install/lock/paths to an asset-type dimension" CLOSED AS OBSOLETE:

#252 originally anticipated a single install module with an `asset_type=` discriminator
parameter (one module handling all asset types at runtime).  The project instead
shipped PARALLEL MODULES PER ASSET TYPE, now fact across four asset types:

  skills       → skill_install.py / skill_lock.py / skill_paths.py
  agents       → agent_install.py / agent_lock.py / agent_paths.py   (PR #268)
  instructions → instructions_install.py / instructions_lock.py / instructions_paths.py
  pi-extension → pi_extension_install.py / pi_extension_lock.py / pi_extension_paths.py

The shared seam is a asset-type-agnostic core (_install_core.py) that each facade binds
via injected callables (canonical_dir_resolver, standard_bundle_link, synthetic_names,
current_linked_resolver).  The lockfile did NOT gain an `asset_type` field — each asset type
has its own lock filename and a per-asset-type path field on the shared LockEntry
(skillPath / agentPath / piExtensionPath).

This dispatcher (get_adapter()) is the single SSOT for the agent asset type's mechanism
catalog — no parallel registry exists.  The `asset_type=` discriminator design is
superseded.  Refs: #252, #268, plan 2026-05-30-agent-asset-type-pr3-5-plan.md § PR3.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.skill_agents import (
    AGENTS,
    UnknownAgentError,
)


class UnsupportedMechanismError(RuntimeError):
    """Harness exists in catalog but its subagent_mechanism is 'none'.

    Means the agent asset type is not installable for this harness — either it
    doesn't support subagents (the 10 by-design cells) or research hasn't
    classified it yet (the 5 unknown cells). Surface to user with the
    matrix URL.
    """


class AgentProjectionConflictError(InstallError):
    """A user-authored file sits at an adapter's destination and would be
    clobbered by install.

    Mirrors `_install_core._symlink_or_copy`'s 'refusing to overwrite
    existing path' posture for the skill path: a foreign file at the
    destination is refused (fail-loud), NOT silently overwritten. The
    facade allows `overwrite=True` only for a TOOL-OWNED slug (one we
    previously wrote, recorded in the lock) so re-install stays idempotent.
    """


def _sentinel_path(dest: Path) -> Path:
    """Return the `.attk` sidecar sentinel path for a given destination file.

    The sentinel (e.g. `config.json` → `.config.json.attk`) marks a file as
    tool-owned. `_guard_foreign` reads it to distinguish our own previously-
    written files (allow refresh) from foreign user files (refuse to clobber).
    Adapters must write the sentinel alongside the main file and remove it on
    uninstall.
    """
    return dest.parent / f".{dest.name}.attk"


def _guard_foreign(dest: Path, *, harness: str, overwrite: bool) -> None:
    """Refuse to clobber a foreign file at `dest` unless overwrite is allowed.

    Two signals permit overwriting a pre-existing file:
      1. `overwrite=True` — the facade confirmed this slug is tool-owned via
         the lock (used by agent_install.apply() when a lock entry exists).
      2. Sentinel present — `.<dest.name>.attk` exists alongside `dest`, written
         by a previous install via this tool. Allows adapter-level re-install
         without requiring the caller to set up a full lock entry (used by
         direct adapter tests and the sentinel-based idempotency contract).

    Foreign files (dest exists, no sentinel, overwrite=False) raise
    AgentProjectionConflictError (an InstallError subclass) so the error
    surfaces as a clean user-facing message, not a bare traceback.
    """
    if overwrite:
        return
    sentinel = _sentinel_path(dest)
    if sentinel.exists():
        return  # our own file — recognised by the .attk sidecar
    if dest.exists() or dest.is_symlink():
        raise AgentProjectionConflictError(
            f"{harness}: refusing to overwrite existing path {dest} — "
            f"a file already exists there that agent-toolkit-cli did not "
            f"install. Move or delete it, then retry."
        )


class AgentAdapter(Protocol):
    """Per-harness install/uninstall contract for the agent asset type.

    Implementations are functions or callable objects; the Protocol is
    structural so we can return module-level callables without wrapping.
    """

    def destination(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> Path:
        """Return the on-disk path this adapter installs to (read-only).

        Lets the facade's agent-aware 'currently linked' scan test whether
        a harness already holds a projection via dest.exists(), since
        adapters write real files rather than symlinks at the skill path.
        """
        ...

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Project the agent definition. Returns the on-disk path created.

        `overwrite=False` (default) refuses to clobber a pre-existing file at
        the destination (raises AgentProjectionConflictError). The facade sets
        `overwrite=True` only when the slug is tool-owned (a lock entry exists),
        so re-installing our own file is idempotent.
        """
        ...

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
    ) -> None:
        """Remove the projection. Idempotent."""
        ...


__all__ = [
    "AgentAdapter",
    "AgentProjectionConflictError",
    "UnsupportedMechanismError",
    "_sentinel_path",
    "get_adapter",
]


def get_adapter(harness_name: str) -> AgentAdapter:
    """Return the adapter for a given harness, dispatched by subagent_mechanism.

    Raises UnknownAgentError if harness_name is not in AGENTS.
    Raises UnsupportedMechanismError if the harness has subagent_mechanism='none'.
    """
    if harness_name not in AGENTS:
        raise UnknownAgentError(harness_name)
    cfg = AGENTS[harness_name]
    mech = cfg.subagent_mechanism
    if mech == "none":
        raise UnsupportedMechanismError(
            f"{harness_name}: subagent_mechanism='none' — not installable. "
            f"See docs/agent-toolkit/harness-matrix.md for supported set."
        )
    if mech == "symlink":
        from agent_toolkit_cli.agent_adapters import symlink
        return symlink.adapter_for(harness_name)
    if mech == "translate":
        from agent_toolkit_cli.agent_adapters import translate
        return translate.adapter_for(harness_name)
    if mech == "config_file_folder":
        from agent_toolkit_cli.agent_adapters import config_file_folder
        return config_file_folder.adapter_for(harness_name)
    raise RuntimeError(f"unreachable: unknown mechanism {mech!r}")
