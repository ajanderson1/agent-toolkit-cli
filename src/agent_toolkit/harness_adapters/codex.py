"""Codex MCP adapter — ConfigFileAdapter against ~/.codex/config.toml.

Round-trip via tomlkit. Managed namespace: `[mcp_servers.<name>]` tables.
The adapter manages only the entries whose names appear in the allow-list;
sibling tables (notice/tui/whatever) and hand-rolled mcp_servers entries are
preserved byte-equal by tomlkit.

Entries added by this adapter are tagged with a `# managed-by-agent-toolkit`
comment inside the table body. This marker is the sole mechanism for
identifying adapter-managed entries on subsequent diff calls — it lets the
adapter remove entries it previously added (when they are absent from the new
allow-list) without requiring a sidecar file.

Refuses MCPs with `transport != "stdio"` — Codex MCP support is stdio-only.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import tomlkit
from tomlkit import TOMLDocument, table
from tomlkit.items import Comment

from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    WriteAction,
)

# Comment placed inside each adapter-managed [mcp_servers.X] table so the
# adapter can identify its own entries on re-reads without a sidecar.
_MANAGED_MARKER = "managed-by-agent-toolkit"


class CodexAdapter:
    name: str = "codex"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".codex" / "config.toml"
        # project: only if .codex/ exists
        codex_dir = project_root / ".codex"
        if not codex_dir.is_dir():
            return None
        return codex_dir / "config.toml"

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        transport = (entry.mcp_spec or {}).get("transport")
        if transport != "stdio":
            raise CannotInstall(
                f"{entry.name}: codex MCP support is stdio-only "
                f"(spec.mcp.transport={transport!r})"
            )

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        """Return names of ALL [mcp_servers.X] tables present in the config."""
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        servers = doc.get("mcp_servers")
        if servers is None:
            return set()
        return set(servers.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        """True iff the on-disk managed entry differs from its template render.

        Compare by rendering the on-disk entry into a one-table doc and the
        template into a one-table doc; bytes-equal = no drift.
        """
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False  # caller checks list_installed for presence
        doc = self._read(target)
        servers_obj = doc.get("mcp_servers")
        on_disk_table = servers_obj.get(entry.name) if servers_obj is not None else None
        if on_disk_table is None:
            return False  # not installed → caller checks list_installed

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
        self, scope: Scope, project_root: Path, entries: list[McpEntry],
    ) -> list[WriteAction]:
        target = self.config_target(scope, project_root)
        if target is None:
            return []  # no target dir; caller treats as no-op for this scope
        desired_names = {e.name for e in entries}

        if not target.is_file():
            new_doc = TOMLDocument()
            self._merge_entries(new_doc, entries, desired_names=desired_names)
            rendered = tomlkit.dumps(new_doc).encode("utf-8")
            return [WriteAction(
                path=target, op="create",
                bytes_before=None, bytes_after=len(rendered),
                contents=rendered,
            )]

        before_bytes = target.read_bytes()
        doc = self._read(target)
        self._merge_entries(doc, entries, desired_names=desired_names)

        after_bytes = tomlkit.dumps(doc).encode("utf-8")
        # tomlkit quirk: deleting the last sub-table from a parsed doc leaves
        # one extra trailing newline.  Strip it when the source didn't have it.
        after_bytes = _fix_trailing_newline(before_bytes, after_bytes)

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
        desired_names: set[str],
    ) -> None:
        """Mutate `doc` so its `[mcp_servers.X]` tables match the desired state.

        - Removes adapter-managed entries (tagged with _MANAGED_MARKER) that
          are no longer in `desired_names`.
        - Upserts all entries in `entries` (alphabetically by name).
        - Hand-rolled entries (no _MANAGED_MARKER) are never touched.
        """
        if "mcp_servers" not in doc:
            doc["mcp_servers"] = table()
        servers = doc["mcp_servers"]

        # Remove adapter-managed entries no longer desired.
        on_disk = list(servers.keys())
        for name in on_disk:
            if name not in desired_names and _is_managed(servers[name]):
                del servers[name]

        # Upsert each desired entry (sorted for determinism).
        for entry in sorted(entries, key=lambda e: e.name):
            new_table = table()
            self._build_entry_table(new_table, entry)
            servers[entry.name] = new_table

    @staticmethod
    def _build_entry_table(t, entry: McpEntry) -> None:
        """Populate `t` with the managed marker + inner-config in Codex shape."""
        cfg = entry.inner_config or {}
        cmd = cfg.get("command")
        if cmd is None:
            raise CannotInstall(
                f"{entry.name}: inner_config.command missing — required for Codex"
            )
        # Marker comment identifies this as an adapter-managed entry.
        t.add(tomlkit.comment(_MANAGED_MARKER))
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


# ---- module-level helpers ----

def _is_managed(tbl) -> bool:
    """Return True iff `tbl` contains the _MANAGED_MARKER comment."""
    container = getattr(tbl, "_value", None)
    if container is None:
        return False
    body = getattr(container, "_body", [])
    for _key, item in body:
        if isinstance(item, Comment):
            # tomlkit.dumps(comment) renders "# text\n"; strip for comparison.
            raw = tomlkit.dumps(item).strip()
            if _MANAGED_MARKER in raw:
                return True
    return False


def _fix_trailing_newline(before: bytes, after: bytes) -> bytes:
    """Work around tomlkit's extra-trailing-newline quirk on last-entry deletion.

    When the last sub-table in a super-table is deleted from a parsed document,
    tomlkit renders one extra ``\\n`` at the end.  Strip it when the source
    didn't end with double-newline but the result does.
    """
    if after.endswith(b"\n\n") and not before.endswith(b"\n\n"):
        return after[:-1]
    return after
