"""Resolve the assets-repo root via the four-step contract.

Resolution order (first match wins):
  1. explicit path (CLI flag)
  2. AGENT_TOOLKIT_REPO env var
  3. walk up from CWD looking for the .agent-toolkit-source marker
  4. ~/GitHub/agent-toolkit/ default

A path is valid iff it is a directory containing both:
  - schemas/asset-frontmatter.v1alpha1.json
  - .agent-toolkit-source

If nothing resolves, raise RepoNotFoundError with an actionable message.
"""
from __future__ import annotations

import os
from pathlib import Path


class RepoNotFoundError(RuntimeError):
    """No assets repo found via the four-step resolution order."""


_MARKER = ".agent-toolkit-source"
_SCHEMA = "schemas/asset-frontmatter.v1alpha1.json"


def _is_assets_repo(path: Path) -> bool:
    return path.is_dir() and (path / _SCHEMA).is_file() and (path / _MARKER).is_file()


def _walk_up_for_marker(start: Path) -> Path | None:
    cur = start.resolve()
    while True:
        if (cur / _MARKER).is_file() and (cur / _SCHEMA).is_file():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def _default_path() -> Path:
    return Path(os.path.expanduser("~/GitHub/agent-toolkit"))


def resolve_repo_root(explicit: Path | None = None) -> Path:
    """Return the assets-repo root or raise RepoNotFoundError."""
    if explicit is not None:
        if _is_assets_repo(explicit):
            return explicit
        raise RepoNotFoundError(
            f"--repo {explicit} is not a valid agent-toolkit assets repo "
            f"(missing {_MARKER} or {_SCHEMA})."
        )

    env = os.environ.get("AGENT_TOOLKIT_REPO")
    if env:
        env_path = Path(env)
        if _is_assets_repo(env_path):
            return env_path
        raise RepoNotFoundError(
            f"AGENT_TOOLKIT_REPO={env} is not a valid agent-toolkit assets repo."
        )

    walked = _walk_up_for_marker(Path.cwd())
    if walked is not None:
        return walked

    default = _default_path()
    if _is_assets_repo(default):
        return default

    raise RepoNotFoundError(
        f"Cannot find an agent-toolkit assets repo. Tried:\n"
        f"  --repo flag: not provided\n"
        f"  $AGENT_TOOLKIT_REPO: {os.environ.get('AGENT_TOOLKIT_REPO', '(unset)')}\n"
        f"  walk-up from {Path.cwd()}: no {_MARKER} marker found\n"
        f"  default {default}: missing or invalid\n\n"
        f"Install the assets repo: git clone https://github.com/ajanderson1/agent-toolkit ~/GitHub/agent-toolkit\n"
        f"Or pass --repo <path> / set AGENT_TOOLKIT_REPO.\n"
        f"Install the CLI: uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli agent-toolkit"
    )
