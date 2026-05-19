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

from agent_toolkit_cli.harness_adapters.base import (
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
        # Return the intended path unconditionally. `diff()` handles the
        # absent-file case by emitting a `create` WriteAction; the dispatch
        # layer's atomic-write helper creates parent dirs as needed. See #125.
        return project_root / ".mcp.json"

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        # Claude supports stdio/sse/http natively; nothing to refuse.
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
        """True iff on-disk single entry differs from its template render.

        Returns False when entry is not installed — callers check
        `list_installed` separately for presence.
        """
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        doc = self._read(target)
        servers = doc.get("mcpServers") or {}
        on_disk = servers.get(entry.name)
        if on_disk is None:
            return False
        template = self._build_entry_dict(entry)
        return on_disk != template

    # ---- diff (the engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        """Reconcile on-disk config to the desired entry set.

        Ownership union: previously_allowed | {e.name for e in entries}.
        Any on-disk mcpServers.<X> whose X is outside this union is preserved.
        """
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
        # Stable formatting: 2-space indent, sorted keys, trailing newline.
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
        """Mutate `doc` so its `mcpServers.<X>` entries match the desired state.

        - Removes managed entries (in `managed_names`) no longer in `desired_names`.
        - Upserts each entry in `entries`.
        - Hand-rolled entries (names NOT in `managed_names`) are preserved.
        - If both `mcpServers` is absent on disk AND no entries → leave doc alone.
        """
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

        # Drop the empty `mcpServers` block if we ended up with nothing — keeps
        # round-trip clean when the only managed entry is unlinked.
        if not doc["mcpServers"]:
            del doc["mcpServers"]

    @staticmethod
    def _build_entry_dict(entry: McpEntry) -> dict:
        """Translate inner_config + mcp_spec into the on-disk Claude shape.

        stdio  → {"type": "stdio", "command", "args"?, "env"?}
        sse/http → {"type": <transport>, "url", "headers"?}
        """
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

        # stdio — same fields as codex
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
