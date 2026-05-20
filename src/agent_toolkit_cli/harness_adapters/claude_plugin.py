"""Claude plugin adapter — ConfigFileAdapter against two JSON files.

Round-trip via `json` stdlib (Python 3.7+ preserves insertion order). Managed
namespaces:

- ``~/.claude/plugins/installed_plugins.json`` ``plugins["<plugin>@<marketplace>"]``
- ``~/.claude/plugins/known_marketplaces.json`` ``<marketplace>``

Toolkit-owned fields (only):
- installed_plugins entry: ``scope``, ``version``. Never touch ``installedAt``,
  ``gitCommitSha``, ``lastUpdated``, ``installPath`` — Claude fills those on
  first start.
- known_marketplaces entry: ``source``. Never touch ``installLocation`` or
  ``lastUpdated``.

Ownership rule (manage by name; spec § "five rules"): we own every
``<plugin>@<marketplace>`` key in ``previously_allowed ∪ desired``. Other
keys are hand-rolled and preserved verbatim.

This adapter has `strategy = "config_file"` because the dispatcher cares
only about the list of WriteActions out of diff(). Internally it writes
TWO files; the per-file diff helpers each emit at most one WriteAction.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    PluginEntry,
    Scope,
    WriteAction,
)


class ClaudePluginAdapter:
    name: str = "claude"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope != "user":
            return None  # v1: project scope unsupported
        home = Path(os.environ.get("HOME", ""))
        return home / ".claude" / "plugins" / "installed_plugins.json"

    def marketplaces_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope != "user":
            return None
        home = Path(os.environ.get("HOME", ""))
        return home / ".claude" / "plugins" / "known_marketplaces.json"

    # ---- pre-flight ----
    def can_install(self, entry: PluginEntry) -> None:
        # No pre-flight refusals in v1. Marketplace-collision detection
        # happens in diff() where we have on-disk state to compare against.
        return

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        plugins_obj = doc.get("plugins") or {}
        return set(plugins_obj.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: PluginEntry) -> bool:
        """True iff the recorded toolkit-owned fields differ from the sidecar.

        For `version: "latest"` we consider any recorded version a non-drift
        (the sidecar is happy to let Claude decide). Pinned versions diff
        on any mismatch.
        """
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        key = f"{entry.plugin}@{entry.marketplace}"
        doc = self._read(target)
        entries = (doc.get("plugins") or {}).get(key) or []
        recorded = next((e for e in entries if e.get("scope") == "user"), None)
        if recorded is None:
            return False
        if entry.version != "latest":
            return recorded.get("version") != entry.version
        return False

    # ---- diff (engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[PluginEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        """Reconcile both JSON files to the desired entry set."""
        target = self.config_target(scope, project_root)
        mkt_target = self.marketplaces_target(scope, project_root)
        if target is None or mkt_target is None:
            return []

        actions: list[WriteAction] = []
        actions.extend(self._diff_installed(target, entries, previously_allowed))
        actions.extend(self._diff_marketplaces(mkt_target, entries, previously_allowed))
        return actions

    # ---- per-file diff helpers ----
    def _diff_installed(
        self,
        target: Path,
        entries: list[PluginEntry],
        previously_allowed: set[str],
    ) -> list[WriteAction]:
        desired_keys = {f"{e.plugin}@{e.marketplace}" for e in entries}
        managed_keys = set(previously_allowed) | desired_keys

        if target.is_file():
            before_bytes = target.read_bytes()
            doc = self._read(target)
        else:
            before_bytes = b""
            doc = {"version": 2, "plugins": {}}

        plugins_obj = doc.setdefault("plugins", {})

        # Remove managed keys no longer desired (user scope only).
        for key in list(plugins_obj.keys()):
            if key in managed_keys and key not in desired_keys:
                remaining = [e for e in plugins_obj[key] if e.get("scope") != "user"]
                if remaining:
                    plugins_obj[key] = remaining
                else:
                    del plugins_obj[key]

        # Upsert desired entries (sorted by key for determinism).
        for entry in sorted(entries, key=lambda e: f"{e.plugin}@{e.marketplace}"):
            key = f"{entry.plugin}@{entry.marketplace}"
            existing_list = plugins_obj.get(key) or []
            user_entry = next((e for e in existing_list if e.get("scope") == "user"), None)
            if user_entry is None:
                # New entry: only toolkit-owned fields.
                new_entry = {"scope": "user", "version": entry.version}
                plugins_obj[key] = [*existing_list, new_entry]
            else:
                # Existing: force-write version only when pinned.
                if entry.version != "latest" and user_entry.get("version") != entry.version:
                    user_entry["version"] = entry.version

        doc.setdefault("version", 2)

        after_bytes = self._dumps(doc).encode("utf-8")
        if after_bytes == before_bytes:
            return []
        if not target.is_file():
            return [WriteAction(path=target, op="create",
                                bytes_before=None, bytes_after=len(after_bytes),
                                contents=after_bytes)]
        return [WriteAction(path=target, op="update",
                            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
                            contents=after_bytes)]

    def _diff_marketplaces(
        self,
        target: Path,
        entries: list[PluginEntry],
        previously_allowed: set[str],
    ) -> list[WriteAction]:
        if target.is_file():
            before_bytes = target.read_bytes()
            doc = self._read(target)
        else:
            before_bytes = b""
            doc = {}

        # Ensure desired marketplaces are present with matching source.
        for entry in entries:
            existing = doc.get(entry.marketplace)
            if existing is None:
                doc[entry.marketplace] = {"source": entry.marketplace_source}
            else:
                existing_source = existing.get("source") or {}
                if existing_source != entry.marketplace_source:
                    raise CannotInstall(
                        f"plugin {entry.name}: marketplace {entry.marketplace!r} "
                        f"already recorded with a different source"
                    )

        # Drop managed marketplaces no longer referenced by any installed plugin.
        if previously_allowed or entries:
            desired_marketplaces = {e.marketplace for e in entries}
            previously_marketplaces = {
                key.rsplit("@", 1)[1]
                for key in previously_allowed
                if "@" in key
            }
            managed_marketplaces = previously_marketplaces | desired_marketplaces
            for name in list(doc.keys()):
                if name in managed_marketplaces and name not in desired_marketplaces:
                    still_used_by_new = any(e.marketplace == name for e in entries)
                    if not still_used_by_new:
                        del doc[name]

        after_bytes = self._dumps(doc).encode("utf-8")
        if after_bytes == before_bytes:
            return []
        if not target.is_file():
            return [WriteAction(path=target, op="create",
                                bytes_before=None, bytes_after=len(after_bytes),
                                contents=after_bytes)]
        return [WriteAction(path=target, op="update",
                            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
                            contents=after_bytes)]

    # ---- helpers ----
    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _dumps(doc: dict) -> str:
        return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
