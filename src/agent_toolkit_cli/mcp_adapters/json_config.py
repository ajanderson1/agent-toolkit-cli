"""JSON-family MCP adapters: claude, pi, opencode.

Each surgically upserts/removes one named entry inside a JSON config document,
preserving every other entry. Per-harness target paths and key translation live
in the per-cell CELLS dict (mechanism = code path; cell = data row).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.mcp_adapters import atomic_write_text


@dataclass(frozen=True)
class _Cell:
    name: str
    user_target: Callable[[Path], Path]
    project_target: Callable[[Path], Path]
    servers_key: str                       # "mcpServers" (claude/pi) | "mcp" (opencode)
    translate: Callable[[dict], dict]      # inner_config -> harness-native entry


def _passthrough(inner: dict) -> dict:
    """Claude/Pi accept the library inner config verbatim."""
    return dict(inner)


# A clean ${VAR} reference: a single ${...} whose body is a bare identifier.
# Anything else (${VAR:-d}, ${VAR:?e}, ${VAR-d}, ${V:1:2}, nested ${A${B}}, …)
# cannot be mechanically mapped to OpenCode's {env:VAR} and must be refused.
_BRACE_EXPR = re.compile(r"\$\{([^}]*)\}")
_CLEAN_VAR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _opencode_translate(inner: dict) -> dict:
    """OpenCode native shape: command joined to a list, env→environment, ${V}→{env:V}.

    Refuses (raises InstallError) rather than silently mistranslate, per the spec's
    governing doctrine (never a silent mistranslation):
      - any env value containing a ${...} that is not a clean bare-variable
        reference (${VAR:-d}, ${VAR:?e}, ${V:1:2}, nested ${A${B}}, …);
      - any server with no `command` (url/remote source) — OpenCode remote
        translation is undefined in this slice, and command:[] would silently
        drop the url.
    """
    if "command" not in inner:
        raise InstallError(
            "opencode: cannot translate this MCP server — it has no `command` "
            "(url/remote source). The OpenCode adapter supports only command-based "
            "(stdio) servers in this slice; url/remote sources are not yet "
            "translatable. Skip --harness opencode for this server."
        )
    cmd = [inner["command"], *inner.get("args", [])]
    out: dict = {"type": "local", "command": cmd}
    env = inner.get("env")
    if isinstance(env, dict):
        translated = {}
        for k, v in env.items():
            if isinstance(v, str):
                for body in _BRACE_EXPR.findall(v):
                    if not _CLEAN_VAR.match(body):
                        raise InstallError(
                            f"opencode: cannot translate env value for {k!r} — "
                            f"only plain ${{VAR}} references are supported, got "
                            f"{v!r}. Adjust the entry or skip --harness opencode."
                        )
                translated[k] = v.replace("${", "{env:")
            else:
                translated[k] = v
        out["environment"] = translated
    return out


CELLS: dict[str, _Cell] = {
    "claude-code": _Cell(
        name="claude-code",
        user_target=lambda home: home / ".claude.json",
        project_target=lambda proj: proj / ".mcp.json",
        servers_key="mcpServers",
        translate=_passthrough,
    ),
    "pi": _Cell(
        name="pi",
        # Pi cell CORRECTED 2026-06-13 (commit 686a8ae, AJ-verified empirical spike):
        # Pi has no native MCP — pi-mcp-adapter reads ~/.pi/agent/mcp.json (user,
        # honors $PI_CODING_AGENT_DIR) and the shared .mcp.json (project).
        user_target=lambda home: home / ".pi" / "agent" / "mcp.json",
        project_target=lambda proj: proj / ".mcp.json",
        servers_key="mcpServers",
        translate=_passthrough,
    ),
    "opencode": _Cell(
        name="opencode",
        user_target=lambda home: home / ".config" / "opencode" / "opencode.json",
        project_target=lambda proj: proj / "opencode.json",
        servers_key="mcp",
        translate=_opencode_translate,
    ),
}


class _JsonAdapter:
    def __init__(self, cell: _Cell) -> None:
        self._cell = cell
        self.name = cell.name

    def config_target(self, *, scope: str, home: Path, project: Path | None = None) -> Path:
        if scope == "global":
            return self._cell.user_target(home)
        if project is None:
            raise ValueError("project scope requires a project root")
        return self._cell.project_target(project)

    def _read(self, path: Path) -> dict:
        """Round-trip read. Absent file or bare {} → {<servers_key>: {}}."""
        key = self._cell.servers_key
        if not path.is_file():
            return {key: {}}
        doc = json.loads(path.read_text(encoding="utf-8") or "{}")
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: expected a JSON object, got {type(doc).__name__}")
        if key not in doc or not isinstance(doc.get(key), dict):
            doc[key] = {}
        return doc

    def install(self, slug, inner_config, *, scope, home, project=None) -> Path:
        target = self.config_target(scope=scope, home=home, project=project)
        doc = self._read(target)
        doc[self._cell.servers_key][slug] = self._cell.translate(inner_config)
        atomic_write_text(target, json.dumps(doc, indent=2) + "\n")
        return target

    def uninstall(self, slug, *, scope, home, project=None) -> None:
        target = self.config_target(scope=scope, home=home, project=project)
        if not target.is_file():
            return
        doc = self._read(target)
        servers = doc[self._cell.servers_key]
        if slug in servers:
            del servers[slug]
            atomic_write_text(target, json.dumps(doc, indent=2) + "\n")

    def is_installed(self, slug, *, scope, home, project=None) -> bool:
        target = self.config_target(scope=scope, home=home, project=project)
        if not target.is_file():
            return False
        doc = self._read(target)
        return slug in doc[self._cell.servers_key]


def adapter_for(harness_name: str) -> _JsonAdapter:
    return _JsonAdapter(CELLS[harness_name])
