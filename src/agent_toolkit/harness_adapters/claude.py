"""Claude MCP adapter — ConfigFileAdapter against ~/.claude.json.

Round-trip via stdlib json. Managed namespace: top-level `mcpServers.<name>`.

Ownership rule (manage by name; same as codex): we own every name in
`previously_allowed ∪ {e.name for e in entries}`. On-disk entries whose names
fall outside that union are hand-rolled and preserved verbatim.

No transport refusal — Claude MCP loader supports stdio, sse, http natively.
The adapter maps `mcp_spec.transport` to the on-disk `type` field.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    WriteAction,
)


class ClaudeAdapter:
    name: str = "claude"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".claude.json"
        target = project_root / ".mcp.json"
        if not target.is_file():
            return None
        return target

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        # Claude supports stdio/sse/http natively; nothing to refuse.
        return None

    # ---- introspection (stubs for now; Task 3) ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        raise NotImplementedError

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        raise NotImplementedError

    # ---- diff (stub for now; Task 2) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        raise NotImplementedError
