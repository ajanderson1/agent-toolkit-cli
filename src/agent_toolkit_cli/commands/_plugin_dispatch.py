"""Dispatcher: orchestrates ClaudePluginAdapter.diff() output into atomic writes + prints.

Mirrors _mcp_dispatch.apply_link but typed for PluginEntry. Reuses the atomic
write engine and loud-print contract from _mcp_dispatch.

The dispatcher is the boundary between the toolkit source-of-truth (the
plugin sidecar at plugins/<slug>.toolkit.yaml) and the harness-projected
config (~/.claude/plugins/{installed_plugins,known_marketplaces}.json).
The adapter never reads the toolkit directory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import IO, Iterable

import yaml

from agent_toolkit_cli.harness_adapters.base import (
    PluginEntry,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)
from agent_toolkit_cli.commands._mcp_dispatch import (
    _execute_action,
    _print_post,
    _print_pre,
)


def _build_plugin_entries(toolkit_root: Path, slugs: Iterable[str]) -> list[PluginEntry]:
    """Resolve slugs → PluginEntry by reading the plugin sidecar / legacy manifest.

    Canonical: ``plugins/<slug>.toolkit.yaml`` with::

        spec:
          source:
            marketplace: <name>
            marketplaceSource: { source: git, url: ... }
            plugin: <plugin-name>
            version: latest | <semver>

    Legacy: ``plugins/<slug>/.claude-plugin/{plugin,marketplace}.json`` with an
    inline ``agent_toolkit_cli`` block of the same shape (best effort).

    Skips slugs whose plugin asset is missing or whose spec.source is incomplete.
    """
    entries: list[PluginEntry] = []
    plugin_root = toolkit_root / "plugins"
    if not plugin_root.is_dir():
        return entries

    for slug in slugs:
        sidecar = plugin_root / f"{slug}.toolkit.yaml"
        meta: dict | None = None
        if sidecar.is_file():
            meta = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
        else:
            # Legacy inline path — read JSON manifest under .claude-plugin/.
            legacy_dir = plugin_root / slug / ".claude-plugin"
            for filename in ("plugin.json", "marketplace.json"):
                legacy = legacy_dir / filename
                if legacy.is_file():
                    doc = json.loads(legacy.read_text(encoding="utf-8"))
                    meta = doc.get("agent_toolkit_cli") or {}
                    break
        if not meta:
            continue
        source = ((meta.get("spec") or {}).get("source")) or {}
        marketplace = source.get("marketplace")
        marketplace_source = source.get("marketplaceSource")
        plugin = source.get("plugin")
        version = source.get("version") or "latest"
        if not (marketplace and marketplace_source and plugin):
            continue
        entries.append(PluginEntry(
            name=slug,
            marketplace=marketplace,
            marketplace_source=dict(marketplace_source),
            plugin=plugin,
            version=version,
        ))
    return entries


def apply_link(
    adapter,
    *,
    scope: Scope,
    project_root: Path,
    entries: list[PluginEntry],
    dry_run: bool,
    stdout: IO[str],
    previously_allowed: set[str] = frozenset(),
) -> list[WriteAction]:
    """Reconcile adapter state to the desired plugin entry set.

    Pre-flight every entry (CannotInstall propagates). In dry-run, prints
    `would-<op>: <path>` per non-unchanged action. In real-run, writes
    bytes atomically and prints the loud-print contract pair.

    `previously_allowed` is the set of on-disk ``<plugin>@<marketplace>``
    keys we own — built from the pre-mutation allowlist by the linker.
    """
    if isinstance(adapter, UnimplementedAdapter):
        return []

    for entry in entries:
        adapter.can_install(entry)

    actions = adapter.diff(
        scope, project_root, entries,
        previously_allowed=previously_allowed,
    )

    if dry_run:
        for act in actions:
            if act.op == "unchanged":
                continue
            print(f"would-{act.op}: {act.path}", file=stdout)
        return actions

    for act in actions:
        if act.op == "unchanged":
            continue
        _print_pre(act, stdout)
        _execute_action(act)
        _print_post(act, stdout)
    return actions


def previously_allowed_keys(
    adapter,
    scope: Scope,
    project_root: Path,
    allowlist_slugs: Iterable[str],
    sidecar_entries: list[PluginEntry],
) -> set[str]:
    """Compute the `previously_allowed` key set for the plugin adapter.

    The adapter owns ``<plugin>@<marketplace>`` keys; we need to translate
    slugs (from the allowlist) into those keys. We compute the union of:
      - keys derived from `sidecar_entries` (slug → plugin@marketplace via sidecar)
      - keys returned by `adapter.list_installed(scope, project_root)`

    The latter ensures hand-edit removals from .agent-toolkit.yaml still get
    pruned (mirrors the MCP/hook reconcile pattern).
    """
    keys = {f"{e.plugin}@{e.marketplace}" for e in sidecar_entries}
    keys |= set(adapter.list_installed(scope, project_root))
    # NOTE: allowlist_slugs is unused directly — the sidecar_entries derived
    # from it already encode the key shape. Accepting it keeps the signature
    # symmetric with the MCP path and reserves room for future per-slug logic.
    _ = allowlist_slugs
    return keys
