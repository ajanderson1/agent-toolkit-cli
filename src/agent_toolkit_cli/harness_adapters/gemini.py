"""Gemini MCP adapter — ConfigFileAdapter against ~/.gemini/settings.json.

Round-trip via stdlib json. Managed namespace: top-level `mcpServers.<name>`.

Ownership rule (manage by name; same as claude/codex/opencode): we own every
name in `previously_allowed | {e.name for e in entries}`. On-disk entries
whose names fall outside that union are hand-rolled and preserved verbatim.

No transport refusal — Gemini's MCP loader supports stdio, sse, http natively
(verified against Gemini CLI v0.39 docs). The adapter maps
`mcp_spec.transport` to the on-disk `type` field. The Gemini on-disk shape
mirrors Claude's: `{"type": "stdio", "command", "args"?, "env"?}` for stdio,
`{"type": "sse"|"http", "url", "headers"?}` for remote transports.

Per-kind behavior for drop-in file paths (not MCP):
  - (gemini, agent): translate (per #97) — Gemini's loader uses zod `.strict()`,
    so emitted frontmatter is name+description ONLY (no agent_toolkit_cli wrapper).
  - (gemini, command): translate — TOML schema (description + prompt).
  - (gemini, skill): symlink (raw wrapper; loader ignores unknown keys).

Reference docs:
  - https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/enterprise.md
    (user/workspace settings.json layout)
  - https://github.com/google-gemini/gemini-cli/blob/main/docs/core/remote-agents.md
    (subagents and MCP entry shape)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    WriteAction,
)


class GeminiAdapter:
    name: str = "gemini"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".gemini" / "settings.json"
        gemini_dir = project_root / ".gemini"
        if not gemini_dir.is_dir():
            return None
        return gemini_dir / "settings.json"

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        return None

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        servers = doc.get("mcpServers")
        if not isinstance(servers, dict):
            return set()
        return set(servers.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        doc = self._read(target)
        servers = doc.get("mcpServers") or {}
        on_disk = servers.get(entry.name)
        if on_disk is None:
            return False
        return on_disk != self._build_entry_dict(entry)

    # ---- diff (the engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        target = self.config_target(scope, project_root)
        if target is None:
            return []
        desired_names = {e.name for e in entries}
        managed_names = set(previously_allowed) | desired_names

        if not target.is_file():
            doc: dict = {}
            self._merge_entries(doc, entries,
                                managed_names=managed_names,
                                desired_names=desired_names)
            rendered = self._dump(doc)
            if not rendered or rendered == b"{}\n":
                return []
            return [WriteAction(
                path=target, op="create",
                bytes_before=None, bytes_after=len(rendered),
                contents=rendered,
            )]

        before_bytes = target.read_bytes()
        doc = self._read(target)
        self._merge_entries(doc, entries,
                            managed_names=managed_names,
                            desired_names=desired_names)
        after_bytes = self._dump(doc)
        if after_bytes == before_bytes:
            return []
        return [WriteAction(
            path=target, op="update",
            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
            contents=after_bytes,
        )]

    # ---- helpers ----
    @staticmethod
    def _read(path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)

    @staticmethod
    def _dump(doc: dict) -> bytes:
        return (
            json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")

    def _merge_entries(
        self,
        doc: dict,
        entries: list[McpEntry],
        *,
        managed_names: set[str],
        desired_names: set[str],
    ) -> None:
        servers = doc.get("mcpServers")
        if servers is None and not entries:
            return

        if "mcpServers" not in doc:
            doc["mcpServers"] = {}
        servers = doc["mcpServers"]

        for name in list(servers.keys()):
            if name in managed_names and name not in desired_names:
                del servers[name]

        for entry in sorted(entries, key=lambda e: e.name):
            servers[entry.name] = self._build_entry_dict(entry)

        if not doc["mcpServers"]:
            del doc["mcpServers"]

    @staticmethod
    def _build_entry_dict(entry: McpEntry) -> dict:
        cfg = entry.inner_config or {}
        spec = entry.mcp_spec or {}
        transport = spec.get("transport") or "stdio"

        if transport in ("sse", "http"):
            url = spec.get("url")
            if not url:
                raise CannotInstall(
                    f"{entry.name}: spec.mcp.url required for transport={transport!r}"
                )
            out: dict = {"type": transport, "url": url}
            headers = spec.get("headers")
            if headers:
                out["headers"] = {str(k): str(v) for k, v in headers.items()}
            return out

        # stdio
        cmd = cfg.get("command")
        if cmd is None:
            raise CannotInstall(
                f"{entry.name}: inner_config.command missing — required for stdio"
            )
        out = {"type": "stdio", "command": cmd}
        if cfg.get("args"):
            out["args"] = list(cfg["args"])
        if cfg.get("env"):
            env_dict = cfg["env"]
            if not isinstance(env_dict, dict):
                raise CannotInstall(
                    f"{entry.name}: inner_config.env must be a dict, "
                    f"got {type(env_dict).__name__}"
                )
            out["env"] = {str(k): str(v) for k, v in env_dict.items()}
        return out
