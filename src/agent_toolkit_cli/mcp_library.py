"""The MCP library at ~/.agent-toolkit/mcps/ — read entries, write entries (add).

Library convention (entries at the library ROOT, no intermediate dir):
`<library>/<slug>/config.json` (inner MCP server config, no mcpServers wrapper)
plus a sibling metadata sidecar at `<library>/<slug>.toolkit.yaml`.
README.md is human prose, not parsed. The library is a plain local store —
NOT a repo clone; the root derives from home, never from _repo_resolution.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True)
class McpAsset:
    slug: str
    inner_config: dict
    metadata: dict = field(default_factory=dict)

    @property
    def transport(self) -> str | None:
        return self.metadata.get("transport")

    @property
    def install_method(self) -> str | None:
        return self.metadata.get("install_method")

    @property
    def env(self) -> list[str]:
        return list(self.metadata.get("env", []))

    @property
    def resolved_version(self) -> str | None:
        """Version transparency: what `add`/`update` last resolved, or None (floating)."""
        return self.metadata.get("resolved_version")


def library_root(home: Path) -> Path:
    """The MCP library root. Derives from home — wheel-safe, no parents[N]."""
    return home / ".agent-toolkit" / "mcps"


def load_mcp_asset(library: Path, slug: str) -> McpAsset:
    """Load one MCP asset by slug. Raises FileNotFoundError if config.json absent."""
    config_path = library / slug / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"MCP '{slug}' not found in the library: {config_path} does not exist — add it first: agent-toolkit-cli mcp add {slug} --npx|--uvx|--docker|--url|--local …"
        )
    inner = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_inner_config(slug, inner, config_path)
    sidecar_path = library / f"{slug}.toolkit.yaml"
    metadata: dict = {}
    if sidecar_path.is_file():
        metadata = yaml.safe_load(sidecar_path.read_text(encoding="utf-8")) or {}
    return McpAsset(slug=slug, inner_config=inner, metadata=metadata)


def _validate_inner_config(slug: str, inner: object, path: Path) -> None:
    """Structural validation — bounds the injection surface to well-typed values.

    The inner config is written into live harness configs where the harness
    EXECUTES it; a malformed shape (command as list, args containing dicts)
    must fail loudly at load time, not propagate into ~/.claude.json.
    """
    if not isinstance(inner, dict):
        raise ValueError(f"{path}: inner config must be a JSON object")
    if "command" in inner and not isinstance(inner["command"], str):
        raise ValueError(f"{path}: 'command' must be a string")
    if "args" in inner and not (
        isinstance(inner["args"], list)
        and all(isinstance(a, str) for a in inner["args"])
    ):
        raise ValueError(f"{path}: 'args' must be a list of strings")
    if "env" in inner and not (
        isinstance(inner["env"], dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in inner["env"].items())
    ):
        raise ValueError(f"{path}: 'env' must be a string→string object")


def list_library(library: Path) -> list[str]:
    """Return sorted slugs of every entry directory containing a config.json."""
    if not library.is_dir():
        return []
    slugs = [
        d.name
        for d in library.iterdir()
        if d.is_dir() and (d / "config.json").is_file()
    ]
    return sorted(slugs)


def write_entry(library: Path, slug: str, *, inner_config: dict, metadata: dict) -> Path:
    """Author one library entry (used by `mcp add`). Returns the entry dir.

    Refuses to overwrite an existing entry unless the caller deleted it first
    (re-`add` of an existing slug is an explicit error; `update` is the verb
    that rewrites entries).
    """
    entry = library / slug
    if (entry / "config.json").is_file():
        raise FileExistsError(f"MCP '{slug}' already exists in the library: {entry}")
    entry.mkdir(parents=True, exist_ok=True)
    (entry / "config.json").write_text(
        json.dumps(inner_config, indent=2) + "\n", encoding="utf-8"
    )
    (entry / "README.md").write_text(f"# {slug}\n", encoding="utf-8")
    (library / f"{slug}.toolkit.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=True), encoding="utf-8"
    )
    return entry
