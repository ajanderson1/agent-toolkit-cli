"""Codex hook adapter — ConfigFileFolderAdapter against ~/.codex/config.toml [hooks].

Round-trip via tomlkit. Managed identity: the handler `command` lives under
`script_root/<slug>/`. Hand-rolled hook entries (command not under script_root)
are preserved verbatim.

User scope only in this PR; project scope returns None (silently skip).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import tomlkit  # noqa: F401  # used by Task 4 (diff/render)
from tomlkit import TOMLDocument, table  # noqa: F401  # used by Task 4

from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    HookEntry,
    Scope,
    WriteAction,
)


_CODEX_HOOK_EVENTS: tuple[str, ...] = (
    "PreToolUse",
    "PostToolUse",
    "PermissionRequest",
    "SessionStart",
    "UserPromptSubmit",
    "Stop",
)


class CodexHookAdapter:
    name: str = "codex"
    strategy: Literal["config_file+folder"] = "config_file+folder"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".codex" / "config.toml"
        return None  # PR1: project scope unsupported

    def script_root(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".codex" / "agent-toolkit-hooks"
        return None  # PR1: project scope unsupported

    # ---- pre-flight ----
    def can_install(self, entry: HookEntry) -> None:
        if not entry.events:
            raise CannotInstall(
                f"{entry.name}: spec.hook.events must declare at least one event"
            )
        unknown = [e for e in entry.events if e not in _CODEX_HOOK_EVENTS]
        if unknown:
            raise CannotInstall(
                f"{entry.name}: unknown codex hook event(s): {unknown!r} "
                f"(expected subset of {_CODEX_HOOK_EVENTS})"
            )
        # Defensive sanity check: command path must contain the slug-specific
        # subdirectory `.codex/agent-toolkit-hooks/<slug>/`. We do NOT anchor
        # to $HOME here — the real ownership-on-disk guarantee is enforced
        # by `diff()` (where scope/project_root are available). This check
        # catches dispatchers that produce wildly wrong paths; it does not
        # prevent every possible weird path. Sufficient as a boundary guard.
        slug_subdir = f".codex/agent-toolkit-hooks/{entry.name}/"
        if slug_subdir not in str(entry.command) + "/":
            home = Path(os.environ.get("HOME", ""))
            expected_prefix = home / ".codex" / "agent-toolkit-hooks" / entry.name
            raise CannotInstall(
                f"{entry.name}: handler command {entry.command!r} must live under "
                f"{expected_prefix!r} (the path-prefix ownership rule depends on this)"
            )

    # ---- introspection (stubs to be filled by Task 4 + Task 5) ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        root = self.script_root(scope, project_root)
        if root is None or not root.is_dir():
            return set()
        return {p.name for p in root.iterdir() if p.is_dir()}

    def entry_drift(self, scope: Scope, project_root: Path, entry: HookEntry) -> bool:
        # Implemented in Task 4 alongside diff().
        raise NotImplementedError

    # ---- diff (Task 4) ----
    def render(self, entries: list[HookEntry]) -> dict[Path, bytes]:
        # Implemented in Task 4.
        raise NotImplementedError

    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[HookEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        # Implemented in Task 4.
        raise NotImplementedError
