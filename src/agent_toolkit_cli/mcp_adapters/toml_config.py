"""Codex TOML-family MCP adapter.

Manages [mcp_servers.<name>] tables in ~/.codex/config.toml (user) /
<project>/.codex/config.toml (project) via tomlkit, preserving all other
tables and comments byte-for-byte.
"""
from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import Table

from agent_toolkit_cli.mcp_adapters import atomic_write_text


class _CodexAdapter:
    name = "codex"

    def config_target(self, *, scope: str, home: Path, project: Path | None = None) -> Path:
        if scope == "global":
            return home / ".codex" / "config.toml"
        if project is None:
            raise ValueError("project scope requires a project root")
        return project / ".codex" / "config.toml"

    def _read(self, path: Path) -> TOMLDocument:
        if not path.is_file():
            return tomlkit.document()
        return tomlkit.parse(path.read_text(encoding="utf-8"))

    def _translate(self, inner: dict) -> dict:
        """Codex mcp_servers entry: command + args + env (+ optional url/transport).
        The library inner shape already matches Codex closely; pass through the
        recognised keys, dropping the library-only 'type' marker.

        Note: Codex's url/StreamableHttp auth keys (bearer_token_env_var,
        http_headers, env_http_headers) are NOT yet forwarded — url sources are
        not authored until a later task; add them to the passthrough when url
        library entries go live (#329 follow-up)."""
        out: dict = {}
        if "command" in inner:
            out["command"] = inner["command"]
        if "args" in inner:
            out["args"] = list(inner["args"])
        if "env" in inner and isinstance(inner["env"], dict):
            out["env"] = dict(inner["env"])
        if "url" in inner:
            out["url"] = inner["url"]
        return out

    def install(self, slug, inner_config, *, scope, home, project=None) -> Path:
        target = self.config_target(scope=scope, home=home, project=project)
        doc = self._read(target)
        if "mcp_servers" not in doc:
            doc["mcp_servers"] = tomlkit.table(is_super_table=True)
        servers = doc["mcp_servers"]
        assert isinstance(servers, Table)  # narrows Item | Container for the index assign
        entry = tomlkit.table()
        for k, v in self._translate(inner_config).items():
            entry[k] = v
        servers[slug] = entry
        atomic_write_text(target, tomlkit.dumps(doc))
        return target

    def uninstall(self, slug, *, scope, home, project=None) -> None:
        target = self.config_target(scope=scope, home=home, project=project)
        if not target.is_file():
            return
        doc = self._read(target)
        servers = doc.get("mcp_servers")
        if servers is not None and slug in servers:
            del servers[slug]
            if len(servers) == 0:
                del doc["mcp_servers"]
            atomic_write_text(target, tomlkit.dumps(doc))

    def is_installed(self, slug, *, scope, home, project=None) -> bool:
        target = self.config_target(scope=scope, home=home, project=project)
        if not target.is_file():
            return False
        servers = self._read(target).get("mcp_servers")
        return servers is not None and slug in servers


def adapter_for(harness_name: str) -> _CodexAdapter:
    assert harness_name == "codex"
    return _CodexAdapter()
