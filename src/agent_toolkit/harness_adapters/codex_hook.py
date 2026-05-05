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

import tomlkit
from tomlkit import TOMLDocument, table

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

    # ---- render: produce script file contents ----
    def render(self, entries: list[HookEntry]) -> dict[Path, bytes]:
        out: dict[Path, bytes] = {}
        for entry in entries:
            for path, data in entry.script_files.items():
                out[path] = data
        return out

    # ---- entry_drift ----
    def entry_drift(self, scope: Scope, project_root: Path, entry: HookEntry) -> bool:
        """True iff on-disk script bytes OR the [hooks] entries differ.

        Returns False when the entry is not installed; the dispatcher checks
        list_installed separately for presence.
        """
        # Script-side drift.
        for path, expected in entry.script_files.items():
            if not path.is_file():
                return True
            if path.read_bytes() != expected:
                return True

        # Config-side drift.
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return True
        doc = self._read(target)
        managed_groups_for_entry = self._collect_managed_groups_for(doc, entry, scope, project_root)
        expected_groups = self._build_groups_for(entry)
        return managed_groups_for_entry != expected_groups

    # ---- diff (the engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[HookEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        target = self.config_target(scope, project_root)
        root = self.script_root(scope, project_root)
        if target is None or root is None:
            return []

        actions: list[WriteAction] = []
        desired_names = {e.name for e in entries}
        managed_names = set(previously_allowed) | desired_names

        # ---- script side ----
        for entry in entries:
            for path, expected in entry.script_files.items():
                if path.is_file():
                    on_disk = path.read_bytes()
                    if on_disk == expected:
                        continue
                    actions.append(WriteAction(
                        path=path, op="update",
                        bytes_before=len(on_disk), bytes_after=len(expected),
                        contents=expected,
                    ))
                else:
                    actions.append(WriteAction(
                        path=path, op="create",
                        bytes_before=None, bytes_after=len(expected),
                        contents=expected,
                    ))

        # Removed entries: every file under root/<slug>/ is a delete.
        for slug in managed_names - desired_names:
            slug_dir = root / slug
            if slug_dir.is_dir():
                for f in slug_dir.iterdir():
                    if f.is_file():
                        actions.append(WriteAction(
                            path=f, op="delete",
                            bytes_before=f.stat().st_size, bytes_after=None,
                            contents=None,
                        ))
                # Drop the empty dir as a separate delete-action — dispatcher
                # handles dir-deletion via the same delete branch.
                actions.append(WriteAction(
                    path=slug_dir, op="delete",
                    bytes_before=0, bytes_after=None,
                    contents=None,
                ))

        # ---- config side ----
        if target.is_file():
            before_bytes = target.read_bytes()
            doc = self._read(target)
        else:
            before_bytes = b""
            doc = TOMLDocument()

        self._merge_hooks(doc, entries, root=root)

        after_bytes = tomlkit.dumps(doc).encode("utf-8")
        # Same trailing-newline strip as the MCP adapter (codex.py:146).
        if after_bytes.endswith(b"\n\n") and not before_bytes.endswith(b"\n\n"):
            after_bytes = after_bytes[:-1]

        if not target.is_file():
            if after_bytes:
                actions.append(WriteAction(
                    path=target, op="create",
                    bytes_before=None, bytes_after=len(after_bytes),
                    contents=after_bytes,
                ))
        elif after_bytes != before_bytes:
            actions.append(WriteAction(
                path=target, op="update",
                bytes_before=len(before_bytes), bytes_after=len(after_bytes),
                contents=after_bytes,
            ))

        return actions

    # ---- internals ----
    @staticmethod
    def _read(path: Path) -> TOMLDocument:
        return tomlkit.parse(path.read_text(encoding="utf-8"))

    def _is_managed_group(self, group, root: Path) -> bool:
        """A group is managed if any of its handlers' command starts with root/."""
        hooks = group.get("hooks") or []
        for h in hooks:
            cmd = h.get("command", "")
            if cmd.startswith(str(root) + "/"):
                return True
        return False

    def _build_groups_for(self, entry: HookEntry) -> dict:
        """Render a {event: matcher_group_dict} for an entry, used by drift checks."""
        out: dict[str, dict] = {}
        for event in entry.events:
            handler: dict = {"type": "command", "command": entry.command}
            if entry.timeout is not None:
                handler["timeout"] = entry.timeout
            if entry.async_:
                handler["async"] = True
            if entry.status_message is not None:
                handler["statusMessage"] = entry.status_message
            group: dict = {"hooks": [handler]}
            if entry.matcher is not None:
                group["matcher"] = entry.matcher
            out[event] = group
        return out

    def _collect_managed_groups_for(self, doc, entry: HookEntry, scope: Scope, project_root: Path) -> dict:
        """Read the existing managed groups belonging to one entry from `doc`."""
        root = self.script_root(scope, project_root)
        out: dict[str, dict] = {}
        hooks_table = doc.get("hooks")
        if hooks_table is None:
            return out
        for event in entry.events:
            arr = hooks_table.get(event) or []
            for g in arr:
                if self._is_managed_group(g, root) and any(
                    h.get("command", "").startswith(
                        str(root / entry.name) + "/"
                    )
                    for h in (g.get("hooks") or [])
                ):
                    # Convert tomlkit objects to plain dicts for comparison.
                    out[event] = {
                        "matcher": g.get("matcher"),
                        "hooks": [dict(h) for h in g.get("hooks") or []],
                    }
                    if out[event]["matcher"] is None:
                        del out[event]["matcher"]
                    break
        return out

    def _merge_hooks(
        self,
        doc: TOMLDocument,
        entries: list[HookEntry],
        *,
        root: Path,
    ) -> None:
        """Mutate `doc[hooks]` so its arrays match the desired entry set.

        - Drops every managed group (handler command starts with root/).
        - Re-emits desired entries' groups, sorted by entry name for determinism.
        - Hand-rolled groups (command not under root/) are preserved.
        - Removes the [hooks] table entirely if no managed and no hand-rolled groups remain.

        Implementation note: we never delete a key and then re-add it — tomlkit
        inserts a spurious leading blank line when that pattern is used on
        array-of-tables keys, breaking byte-equal round-trips. Instead we
        compute the final array for each event and do a single assignment.
        """
        # Ensure [hooks] exists if we have entries to write.
        if "hooks" not in doc and not entries:
            return
        if "hooks" not in doc:
            doc["hooks"] = table()
        hooks_table = doc["hooks"]

        # Build the desired managed groups per event, sorted by entry name for determinism.
        desired_groups: dict[str, list] = {}  # event -> list of new groups
        for entry in sorted(entries, key=lambda e: e.name):
            for event in entry.events:
                handler = table()
                handler["type"] = "command"
                handler["command"] = entry.command
                if entry.timeout is not None:
                    handler["timeout"] = entry.timeout
                if entry.async_:
                    handler["async"] = True
                if entry.status_message is not None:
                    handler["statusMessage"] = entry.status_message

                group = table()
                if entry.matcher is not None:
                    group["matcher"] = entry.matcher
                group["hooks"] = [handler]

                desired_groups.setdefault(event, []).append(group)

        # For every event that has existing content OR new managed groups,
        # compute survivors (hand-rolled) + new managed groups and assign once.
        # Using a single assignment avoids the tomlkit leading-\n artifact that
        # appears when a key is deleted then re-added.
        all_events = set(_CODEX_HOOK_EVENTS) | set(desired_groups)
        for event in all_events:
            existing = hooks_table.get(event) or []
            survivors = [g for g in existing if not self._is_managed_group(g, root)]
            new_managed = desired_groups.get(event, [])
            final = survivors + new_managed
            if final:
                hooks_table[event] = final
            elif hooks_table.get(event) is not None:
                # The event key exists but its array became empty — remove it.
                # Only delete when we know the key was already there to avoid
                # the tomlkit leading-\n artifact on absent keys.
                del hooks_table[event]

        # If [hooks] became empty, remove it.
        empty = all(
            (hooks_table.get(e) is None or len(hooks_table.get(e)) == 0)
            for e in _CODEX_HOOK_EVENTS
        )
        if empty:
            del doc["hooks"]
