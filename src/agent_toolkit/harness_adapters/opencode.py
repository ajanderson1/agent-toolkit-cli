"""OpenCode MCP adapter — ConfigFileAdapter against ~/.config/opencode/opencode.json.

Round-trip via stdlib json. Managed namespace: top-level `mcp.<name>`.

Ownership rule (manage by name; same as codex/claude): we own every name in
`previously_allowed ∪ {e.name for e in entries}`. On-disk entries whose names
fall outside that union are hand-rolled and preserved verbatim.

Entry shape (from https://opencode.ai/docs/mcp-servers/):
  - stdio  → {"type": "local",  "command": [...], "environment": {...}, "enabled": True}
  - http   → {"type": "remote", "url": ..., "headers": {...}, "enabled": True}
  - sse    → {"type": "remote", "url": ..., "headers": {...}, "enabled": True}

Note on `enabled`: managed entries are always rendered as `enabled: True`. If a
user hand-edits an MCP entry's `enabled: False`, the next reconcile (link/fix)
re-aligns it. To disable an MCP, remove it from the allowlist instead.

No transport refusal — all three transports map to a valid on-disk shape.
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


class OpenCodeAdapter:
    name: str = "opencode"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".config" / "opencode" / "opencode.json"
        opencode_dir = project_root / ".opencode"
        if not opencode_dir.is_dir():
            return None
        return opencode_dir / "opencode.json"

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        return None

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        servers = doc.get("mcp")
        if not isinstance(servers, dict):
            return set()
        return set(servers.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        doc = self._read(target)
        servers = doc.get("mcp") or {}
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
        servers = doc.get("mcp")
        if servers is None and not entries:
            return

        if "mcp" not in doc:
            doc["mcp"] = {}
        servers = doc["mcp"]

        for name in list(servers.keys()):
            if name in managed_names and name not in desired_names:
                del servers[name]

        for entry in sorted(entries, key=lambda e: e.name):
            servers[entry.name] = self._build_entry_dict(entry)

        if not doc["mcp"]:
            del doc["mcp"]

    @staticmethod
    def _build_entry_dict(entry: McpEntry) -> dict:
        cfg = entry.inner_config or {}
        spec = entry.mcp_spec or {}
        transport = spec.get("transport") or "stdio"

        if transport in ("http", "sse"):
            url = spec.get("url")
            if not url:
                raise CannotInstall(
                    f"{entry.name}: spec.mcp.url required for transport={transport!r}"
                )
            out: dict = {
                "type": "remote",
                "url": url,
                "enabled": True,
            }
            headers = spec.get("headers")
            if headers:
                out["headers"] = {str(k): str(v) for k, v in headers.items()}
            return out

        # stdio → local
        cmd = cfg.get("command")
        if cmd is None:
            raise CannotInstall(
                f"{entry.name}: inner_config.command missing — required for stdio"
            )
        # OpenCode merges command + args into a single list.
        full_command: list[str] = [str(cmd)]
        if cfg.get("args"):
            full_command.extend(str(a) for a in cfg["args"])
        out = {
            "type": "local",
            "command": full_command,
            "enabled": True,
        }
        if cfg.get("env"):
            env_dict = cfg["env"]
            if not isinstance(env_dict, dict):
                raise CannotInstall(
                    f"{entry.name}: inner_config.env must be a dict, "
                    f"got {type(env_dict).__name__}"
                )
            out["environment"] = {str(k): str(v) for k, v in env_dict.items()}
        return out
