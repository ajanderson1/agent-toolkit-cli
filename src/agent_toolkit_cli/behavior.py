"""Small shared CLI/TUI behavior configuration (not presentation settings)."""
from __future__ import annotations

import json
from pathlib import Path

from agent_toolkit_cli._install_core import InstallError


def _read_config(home: Path | None = None) -> dict:
    path = (home or Path.home()) / ".agent-toolkit" / "config.json"
    try:
        config = json.loads(path.read_text())
    except FileNotFoundError:
        config = {}
    except (OSError, ValueError) as exc:
        raise InstallError(f"Invalid behavior configuration {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise InstallError(f"Invalid behavior configuration {path}: expected an object")
    return config


def project_backing(*, home: Path | None = None, creating: bool = True) -> str:
    config = _read_config(home)
    backing = config.get("projectBacking", "central")
    enabled = config.get("allowIsolatedProjects", False)
    if backing not in ("central", "isolated") or not isinstance(enabled, bool):
        raise InstallError("Invalid behavior configuration: projectBacking must be central/isolated and allowIsolatedProjects must be boolean")
    if creating and backing == "isolated" and not enabled:
        raise InstallError("New isolated project backing is disabled; deliberately set allowIsolatedProjects=true to enable it")
    return backing
