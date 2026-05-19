"""Codex MCP adapter — ConfigFileAdapter against ~/.codex/config.toml.

Round-trip via tomlkit. Managed namespace: `[mcp_servers.<name>]` tables.

Ownership rule (manage by name; spec § "five rules"): we own every name in
`previously_allowed ∪ {e.name for e in entries}`. On-disk tables whose names
fall outside that union are hand-rolled and preserved verbatim.

Codex MCP supports both stdio and streamable HTTP transports. The toolkit's
`spec.mcp.transport` ∈ {stdio, http, sse}; stdio maps to `command`/`args`/`env`
and http maps to `url`/`http_headers` (Codex's TOML field name — toolkit's
`spec.mcp.headers` is renamed on render). SSE is refused — deprecated upstream.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import tomlkit
from tomlkit import TOMLDocument, table

from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    WriteAction,
)


class CodexAdapter:
    name: str = "codex"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".codex" / "config.toml"
        # Return the intended path unconditionally. `diff()` handles the
        # absent-file case by emitting a `create` WriteAction; the dispatch
        # layer's atomic-write helper creates parent dirs (`.codex/`) as
        # needed. See #125.
        return project_root / ".codex" / "config.toml"

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        transport = (entry.mcp_spec or {}).get("transport") or "stdio"
        if transport == "sse":
            raise CannotInstall(
                f"{entry.name}: codex does not support SSE transport "
                f"(use transport=http for streamable HTTP MCPs)"
            )

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        """Names of every [mcp_servers.X] table in the config (managed or not)."""
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        servers = doc.get("mcp_servers")
        if servers is None:
            return set()
        return set(servers.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        """True iff the on-disk single entry differs from its template render.

        Returns False when the entry is not installed — callers check
        `list_installed` separately for presence.
        """
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        doc = self._read(target)
        servers_obj = doc.get("mcp_servers")
        on_disk_table = servers_obj.get(entry.name) if servers_obj is not None else None
        if on_disk_table is None:
            return False

        on_disk_doc = TOMLDocument()
        on_disk_servers = table()
        on_disk_servers.append(entry.name, on_disk_table)
        on_disk_doc.append("mcp_servers", on_disk_servers)
        on_disk_bytes = tomlkit.dumps(on_disk_doc).encode("utf-8")

        template_doc = TOMLDocument()
        template_servers = table()
        template_table = table()
        self._build_entry_table(template_table, entry)
        template_servers.append(entry.name, template_table)
        template_doc.append("mcp_servers", template_servers)
        template_bytes = tomlkit.dumps(template_doc).encode("utf-8")

        return on_disk_bytes != template_bytes

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

        `previously_allowed` is the set of names that were in the allow-list
        before this dispatch's mutation (or empty for first-time link / `fix`
        reconcile). Together with the names in `entries`, it defines our
        ownership: any on-disk `[mcp_servers.X]` whose `X` is outside this
        union is hand-rolled and never touched.
        """
        target = self.config_target(scope, project_root)
        if target is None:
            return []
        desired_names = {e.name for e in entries}
        managed_names = set(previously_allowed) | desired_names

        if not target.is_file():
            new_doc = TOMLDocument()
            self._merge_entries(new_doc, entries,
                                managed_names=managed_names,
                                desired_names=desired_names)
            rendered = tomlkit.dumps(new_doc).encode("utf-8")
            if not rendered:
                # Empty doc — nothing to write.
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

        after_bytes = tomlkit.dumps(doc).encode("utf-8")

        # Defensive: tomlkit may emit an extra trailing newline when a sub-table
        # is removed and a sibling super-table key remains last. The blank line
        # between the deleted key and its predecessor is retained. Strip it so
        # the round-trip remains byte-equal to the original source.
        # Condition: after ends with \n\n but before (the source we read) ends
        # with a single \n — the extra \n is always a tomlkit artifact.
        if after_bytes.endswith(b"\n\n") and not before_bytes.endswith(b"\n\n"):
            after_bytes = after_bytes[:-1]

        if after_bytes == before_bytes:
            return []
        return [WriteAction(
            path=target, op="update",
            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
            contents=after_bytes,
        )]

    # ---- helpers ----
    @staticmethod
    def _read(path: Path) -> TOMLDocument:
        return tomlkit.parse(path.read_text(encoding="utf-8"))

    def _merge_entries(
        self,
        doc: TOMLDocument,
        entries: list[McpEntry],
        *,
        managed_names: set[str],
        desired_names: set[str],
    ) -> None:
        """Mutate `doc` so its `[mcp_servers.X]` tables match the desired state.

        - Removes managed entries (those in `managed_names`) that are no longer
          in `desired_names`.
        - Upserts each entry in `entries` (alphabetically by name).
        - Hand-rolled entries (names NOT in `managed_names`) are preserved.
        """
        servers_obj = doc.get("mcp_servers")

        # If there's nothing to do AND no mcp_servers table exists, do nothing.
        # Avoids creating an empty `[mcp_servers]` super-table on a no-op.
        if servers_obj is None and not entries:
            return

        if "mcp_servers" not in doc:
            doc["mcp_servers"] = table()
        servers = doc["mcp_servers"]

        # Remove managed entries no longer desired.
        on_disk = list(servers.keys())
        for name in on_disk:
            if name in managed_names and name not in desired_names:
                del servers[name]

        # Upsert each desired entry (sorted for deterministic key order across runs).
        for entry in sorted(entries, key=lambda e: e.name):
            new_table = table()
            self._build_entry_table(new_table, entry)
            servers[entry.name] = new_table

    @staticmethod
    def _build_entry_table(t, entry: McpEntry) -> None:
        """Populate `t` with the inner-config translated to Codex shape.

        stdio → command/args/env keys.
        http  → url/http_headers keys (Codex's TOML field name for headers).
        """
        cfg = entry.inner_config or {}
        spec = entry.mcp_spec or {}
        transport = spec.get("transport") or "stdio"

        if transport == "http":
            url = spec.get("url")
            if not url:
                raise CannotInstall(
                    f"{entry.name}: spec.mcp.url required for transport='http'"
                )
            t["url"] = url
            headers = spec.get("headers")
            if headers:
                if not isinstance(headers, dict):
                    raise CannotInstall(
                        f"{entry.name}: spec.mcp.headers must be a dict, "
                        f"got {type(headers).__name__}"
                    )
                t["http_headers"] = {str(k): str(v) for k, v in headers.items()}
            return

        # stdio
        cmd = cfg.get("command")
        if cmd is None:
            raise CannotInstall(
                f"{entry.name}: inner_config.command missing — required for Codex stdio"
            )
        t["command"] = cmd
        if "args" in cfg and cfg["args"]:
            t["args"] = list(cfg["args"])
        if "env" in cfg and cfg["env"]:
            env_dict = cfg["env"]
            if not isinstance(env_dict, dict):
                raise CannotInstall(
                    f"{entry.name}: inner_config.env must be a dict, "
                    f"got {type(env_dict).__name__}"
                )
            t["env"] = {str(k): str(v) for k, v in env_dict.items()}
