"""agent-toolkit-tui — Textual cockpit for the agent-toolkit CLI.

Sister to bin/agent-toolkit. Read side imports agent_toolkit; write side shells
out to the bash CLI. Never touches the filesystem directly.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__: str = _pkg_version("agent-toolkit")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["__version__"]
