"""Per-harness MCP projection adapters, dispatched by harness name.

MCP is config-injection-shaped: each adapter surgically upserts/removes ONE
named entry inside the harness's native config file, preserving every other
byte (Rule 2 of the design spec: manage by name, never by file ownership).

Two mechanism modules:
  - json_config: claude / pi / opencode — mcpServers.<name> in a JSON document.
  - toml_config: codex — [mcp_servers.<name>] in a TOML document (tomlkit).

get_adapter() is the single SSOT for the harness → mechanism map. No parallel
registry exists. Mirrors agent_adapters/__init__.py.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal, Protocol

from agent_toolkit_cli._install_core import InstallError


class UnsupportedMcpHarnessError(InstallError):
    """Harness has no MCP adapter (not one of claude/codex/opencode/pi)."""


# Harness → mechanism module. The single SSOT.
_MECHANISM: dict[str, Literal["json", "toml"]] = {
    "claude-code": "json",
    "pi": "json",
    "standard": "json",
    "opencode": "json",
    "codex": "toml",
}


def atomic_write_text(target: Path, content: str) -> None:
    """Write `content` to `target` atomically (temp file in same dir → os.replace).

    Same-directory staging guarantees atomicity across filesystems. Creates
    parent directories if absent.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


class McpAdapter(Protocol):
    """Per-harness install/uninstall contract for the MCP kind."""

    name: str

    def config_target(self, *, scope: str, home: Path, project: Path | None = None) -> Path:
        """The config file this adapter mutates (round-trip), e.g. ~/.codex/config.toml."""
        ...

    def install(
        self,
        slug: str,
        inner_config: dict,
        *,
        scope: str,
        home: Path,
        project: Path | None = None,
    ) -> Path:
        """Upsert the named MCP entry into the harness config. Returns the path written.

        Idempotent: re-running with the same inner_config produces a byte-identical
        managed entry. Creates the config file with a valid empty shape if absent.
        """
        ...

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path,
        project: Path | None = None,
    ) -> None:
        """Remove the named MCP entry. Idempotent (no-op if absent). Leaves all
        other entries and the surrounding document byte-equal."""
        ...

    def is_installed(
        self,
        slug: str,
        *,
        scope: str,
        home: Path,
        project: Path | None = None,
    ) -> bool:
        """True if the named entry currently exists in the harness config."""
        ...


def get_adapter(harness_name: str) -> McpAdapter:
    """Return the MCP adapter for a harness. SSOT dispatch by mechanism family."""
    mech = _MECHANISM.get(harness_name)
    if mech is None:
        raise UnsupportedMcpHarnessError(
            f"{harness_name}: no MCP adapter — supported harnesses are "
            f"{', '.join(sorted(_MECHANISM))}."
        )
    if mech == "json":
        import agent_toolkit_cli.mcp_adapters.json_config as json_config
        return json_config.adapter_for(harness_name)
    if mech == "toml":
        import agent_toolkit_cli.mcp_adapters.toml_config as toml_config
        return toml_config.adapter_for(harness_name)
    raise RuntimeError(f"unreachable: unknown mechanism {mech!r}")


__all__ = [
    "McpAdapter",
    "UnsupportedMcpHarnessError",
    "atomic_write_text",
    "get_adapter",
]
