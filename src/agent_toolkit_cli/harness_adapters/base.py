"""Base types and Protocols for harness MCP adapters.

Three strategy Protocols (PluginFolderAdapter, ConfigFileAdapter,
ConfigFileFolderAdapter) plus a common base. Adapters implement exactly
one strategy.

See docs/superpowers/specs/2026-05-04-mcp-adapters-design.md § "Two Protocols"
for the rationale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable


Scope = Literal["user", "project"]


@dataclass(frozen=True)
class McpEntry:
    """One catalog MCP entry, ready for adapter consumption.

    `name` is the toolkit-repo directory name (the canonical id).
    `inner_config` is the verbatim parsed `mcps/<name>/config.json`.
    `mcp_spec` is the `spec.mcp` block from the sibling README.md frontmatter.
    """
    name: str
    inner_config: dict
    mcp_spec: dict


@dataclass(frozen=True)
class HookEntry:
    """One hook asset, ready for adapter consumption.

    `name` is the asset slug (the canonical id).
    `events` is the tuple of Codex hook events this asset binds to.
    `command` is the absolute path the [hooks] handler will reference
    (under script_root/<slug>/, materialised by the dispatcher).
    `script_files` maps absolute destination paths to their byte contents.
    """
    name: str
    events: tuple[str, ...]
    command: str
    matcher: str | None = None
    timeout: int | None = None
    async_: bool = False
    status_message: str | None = None
    script_files: dict[Path, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginEntry:
    """One catalog plugin entry, ready for adapter consumption.

    `name` is the toolkit slug (canonical id).
    `marketplace` is the short name keying into known_marketplaces.json.
    `marketplace_source` is the verbatim `spec.source.marketplaceSource` block
    — uses Claude's on-disk key `source` (not `type`).
    `plugin` is the plugin name as known to the marketplace.
    `version` is `"latest"` or a pinned semver string.
    """
    name: str
    marketplace: str
    marketplace_source: dict
    plugin: str
    version: str


@dataclass(frozen=True)
class WriteAction:
    """Describes a single filesystem mutation produced by an adapter.

    Carries `contents` (rendered desired bytes) so the dispatcher can write
    atomically without re-rendering. None on `delete` (nothing to write).
    """
    path: Path
    op: Literal["create", "update", "delete", "unchanged"]
    bytes_before: int | None
    bytes_after: int | None
    contents: bytes | None


class CannotInstall(Exception):
    """Pre-flight refusal raised by adapter.can_install().

    Caller catches and skips the offending entry, proceeding with siblings.
    Matches the existing exception-raising pattern in the codebase
    (e.g. _yaml_edit.add_slug → ValueError, walker → yaml.YAMLError).
    """


@runtime_checkable
class PluginFolderAdapter(Protocol):
    """Strategy: own a folder outright (e.g. ~/.claude/plugins/agent-toolkit/)."""

    name: str
    strategy: Literal["plugin_folder"]

    def can_install(self, entry: McpEntry) -> None: ...
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]: ...
    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool: ...
    def plugin_target(self, scope: Scope, project_root: Path) -> Path: ...
    def render(self, entries: list[McpEntry]) -> dict[Path, bytes]: ...
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]: ...


@runtime_checkable
class ConfigFileAdapter(Protocol):
    """Strategy: surgically mutate a single named config file (round-trip)."""

    name: str
    strategy: Literal["config_file"]

    def can_install(self, entry: McpEntry) -> None: ...
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]: ...
    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool: ...
    def config_target(self, scope: Scope, project_root: Path) -> Path: ...
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]: ...


@runtime_checkable
class ConfigFileFolderAdapter(Protocol):
    """Hybrid strategy: own a folder of artefacts AND mutate a single config file.

    Adapter materialises files under `script_root` and surgically edits
    `config_target`. Both are mutated in one `diff()` call so they commit
    or rollback together.
    """

    name: str
    strategy: Literal["config_file+folder"]

    def can_install(self, entry: HookEntry) -> None: ...
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]: ...
    def entry_drift(self, scope: Scope, project_root: Path, entry: HookEntry) -> bool: ...
    def config_target(self, scope: Scope, project_root: Path) -> Path | None: ...
    def script_root(self, scope: Scope, project_root: Path) -> Path | None: ...
    def render(self, entries: list[HookEntry]) -> dict[Path, bytes]: ...
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[HookEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]: ...


class UnimplementedAdapter:
    """Returned by `get_adapter()` for (harness, kind) pairs whose adapter
    has not landed.

    Loud-skip semantics: callers detect this via `isinstance(...,
    UnimplementedAdapter)` and print `skip_message()` before continuing.

    The `kind` attribute (defaults to `"mcp"` for back-compat) is what the
    sentinel was asked for. It shapes the skip message so the user isn't
    told "no MCP adapter" when they actually asked for a different adapter
    kind (issue #123).
    """
    name: str
    kind: str
    strategy: Literal["unimplemented"] = "unimplemented"

    def __init__(self, name: str, kind: str = "mcp") -> None:
        self.name = name
        self.kind = kind

    def skip_message(self) -> str:
        # Preserve the historical "MCP" capitalisation for the default kind so
        # existing log greps and tests continue to match. Other kinds get the
        # lowercase canonical name as it appears in `ALL_KINDS`.
        label = "MCP" if self.kind == "mcp" else self.kind
        return f"no {label} adapter for harness {self.name} yet — skipping"
