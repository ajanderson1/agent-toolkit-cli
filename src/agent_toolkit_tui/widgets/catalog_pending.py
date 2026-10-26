"""Bind catalogue-only Git toggles to their original subscription and selector."""
from dataclasses import replace
from pathlib import Path
import subprocess
from shlex import join

from rich.markup import escape


class CatalogPendingMixin:
    def _capture_catalog_pending(self):
        intents = getattr(self, "_catalog_pending", {})
        intents = {key: value for key, value in intents.items() if self._pending.get(key) == "link"}
        for key, op in self._pending.items():
            row = next((row for row in self._rows if row.slug == key[-1]), None)
            if op == "link" and row is not None and row.catalog_only and row.catalog_item.source_type == "git":
                intents.setdefault(key, (row.catalog_url, row.catalog_ref, row.catalog_item))
        self._catalog_pending = intents

    def pending_catalog_entries(self):
        return {key: value for key, value in getattr(self, "_catalog_pending", {}).items()
                if self._pending.get(key) == "link"}

    def restore_catalog_pending(self, intents):
        self._catalog_pending = {key: value for key, value in intents.items() if self._pending.get(key) == "link"}

    def _catalog_info(self, row):
        return catalog_info(row, scope=self._scope, kind=self.catalog_kind)


def catalog_info(row, *, scope, kind):
    from agent_toolkit_cli.asset_catalog_ops import backing_modules
    from agent_toolkit_cli.skill_catalog import CatalogEntry, safe_source, run_git
    item, url = row.catalog_item, row.catalog_url
    entry, canonical, actual_scope = None, None, scope
    if not row.catalog_only and getattr(row, "origin", "") != "npm":
        locks, paths, _, canonical_dir = backing_modules(kind)
        project = Path.cwd() if scope == "project" else None
        scoped = locks.read_lock(paths.lock_file_path(scope=scope, home=Path.home(), project=project)).skills
        entry = scoped.get(row.slug)
        if entry is None:
            entry = locks.read_lock(paths.library_lock_path()).skills.get(row.slug)
            actual_scope, project = "global", None
        if entry is not None:
            canonical = canonical_dir(row.slug, scope=actual_scope, home=Path.home(), project=project)
            provenance = entry.extras.get("catalog")
            if item is None and isinstance(provenance, dict):
                try:
                    source = replace(safe_source(provenance["source"]),
                        subpath=provenance["path"], ref=provenance.get("ref"))
                    item = CatalogEntry(provenance["key"], row.description, source,
                        kind=kind, entry_file=provenance.get("entryFile"))
                    url = provenance["url"]
                except (KeyError, ValueError, TypeError):
                    pass
    if item is None:
        return []
    lines = [f"Catalog: {url}", f"Description: {item.description}",
             f"Kind: {item.kind}; source type: {item.source_type}"]
    if row.catalog_warning:
        lines.append(row.catalog_warning)
    if item.source_type == "npm":
        lines += [f"Requested source: {item.npm_source}",
                  "Not installed; catalogue browsing never downloads packages." if row.catalog_only else "Native installation and selection remain authoritative.",
                  "Explicit native installation: " + join(["agent-toolkit-cli", "pi-extensions", "catalog", "install", item.key, "--scope", scope]),
                  "Installation may execute lifecycle scripts and activate bundled resources; confirmation is required."]
    else:
        lines += [f"Upstream: {item.source.url}", f"Directory: {item.source.subpath}", f"Ref: {item.source.ref or '(default)'}"]
        if item.entry_file:
            lines.append(f"Agent entry file: {item.entry_file}")
        group = {"agent": "agents", "command": "commands", "pi-extension": "pi-extensions"}[item.kind]
        if row.catalog_only:
            lines += ["Not acquired; no harness exposure. Space queues acquisition and exposure for Apply.",
                      "Add without enabling: " + join(["agent-toolkit-cli", group, "catalog", "add", item.key])]
        else:
            from agent_toolkit_cli.asset_update_check import read_check
            if canonical is not None:
                lines += [f"Local backing ({actual_scope}): {canonical}"]
                try:
                    lines.append("Local revision: " + run_git(["rev-parse", "HEAD"], cwd=canonical))
                except (ValueError, OSError, subprocess.SubprocessError):
                    lines.append("Local revision: unavailable")
            observation = read_check(kind, row.slug, scope=actual_scope, home=Path.home(),
                project=Path.cwd() if actual_scope == "project" else None) if entry is not None else None
            lines.append(f"Upstream check: {observation['status']} · checked {observation['checked_at']}" if observation else "Upstream: not checked")
            flag = "-g" if actual_scope == "global" else "-p"
            lines += ["Check: " + join(["agent-toolkit-cli", group, "check", row.slug, flag]),
                      "Update: " + join(["agent-toolkit-cli", group, "update", row.slug, flag]),
                      "Existing update/backing limitations apply; catalogue refresh never updates content."]
    return [escape(line) for line in lines]
