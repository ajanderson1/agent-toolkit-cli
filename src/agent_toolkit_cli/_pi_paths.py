"""Pi filesystem path resolver.

Single module so a Pi version bump (path layout changes) is one diff.
Project scope omits the `/agent/` infix; see _support.py:55-60 for the rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PiPaths:
    home: Path
    project_root: Path

    # ---- user scope ----
    @property
    def user_extensions_dir(self) -> Path:
        return self.home / ".pi" / "agent" / "extensions"

    @property
    def user_settings_json(self) -> Path:
        return self.home / ".pi" / "agent" / "settings.json"

    @property
    def user_node_modules_dir(self) -> Path:
        return self.home / ".pi" / "agent" / "npm" / "node_modules"

    # ---- project scope ----
    @property
    def project_extensions_dir(self) -> Path:
        return self.project_root / ".pi" / "extensions"

    @property
    def project_settings_json(self) -> Path:
        return self.project_root / ".pi" / "settings.json"

    @property
    def project_node_modules_dir(self) -> Path:
        return self.project_root / ".pi" / "npm" / "node_modules"
