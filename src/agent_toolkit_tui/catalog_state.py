"""Pure catalogue joins shared by the three additional asset grids."""
from dataclasses import dataclass, replace
from pathlib import Path

from agent_toolkit_cli.asset_catalog_ops import backing_modules, catalog_target, entry_identity, validate_targets
from agent_toolkit_cli.skill_catalog import CatalogEntry, CatalogSnapshot, npm_identity


@dataclass(kw_only=True)
class CatalogFields:
    catalog_item: CatalogEntry | None = None
    catalog_url: str = ""
    catalog_ref: str | None = None
    catalog_warning: str = ""
    catalog_only: bool = False
    description: str = ""


def merge_catalog_rows(kind, rows, snapshot, *, scope, home, project, selection=None):
    if snapshot is None or snapshot.error:
        return rows
    if kind == "pi-extension":
        return _merge_pi_rows(rows, snapshot)
    from agent_toolkit_tui.agent_state import AgentRow, AgentCell, interactive_harnesses as agent_harnesses
    from agent_toolkit_tui.command_state import CommandRow, CommandCell, interactive_harnesses as command_harnesses
    row_class, cell_class, harnesses = (AgentRow, AgentCell, agent_harnesses) if kind == "agent" else (CommandRow, CommandCell, command_harnesses)
    locks, paths, _, _ = backing_modules(kind)
    library = locks.read_lock(paths.library_lock_path()).skills
    scoped = locks.read_lock(paths.lock_file_path(scope=scope, home=home, project=project)).skills
    result = list(rows)
    for item in snapshot.for_kind(kind):
        slug, warning = catalog_target(library, item, snapshot.url)
        existing = next((row for row in result if row.slug == (slug or item.key)), None)
        if existing is not None:
            if slug is None:
                warning = f"{item.key}: catalog conflicts with unmanaged/scoped local content; existing content retained"
            elif slug in scoped and entry_identity(kind, slug, scoped[slug]) != item.selector:
                warning = f"{slug}: scoped backing conflicts with catalog; existing content retained"
            result[result.index(existing)] = replace(existing, catalog_item=item,
                catalog_url=snapshot.url, catalog_ref=snapshot.ref,
                catalog_warning=warning, description=item.description)
            continue
        if warning:
            continue
        cells = {}
        for target in harnesses(scope, selection):
            try:
                validate_targets(item, (target,), scope=scope, home=home or Path.home(), project=project)
            except (ValueError, RuntimeError):
                continue
            cells[(target, scope)] = cell_class(linked=False)
        result.append(row_class(slug=item.key, source=item.source.url, ref=item.source.ref or "(default)",
            state="catalog", cells=cells, catalog_item=item, catalog_url=snapshot.url,
            catalog_ref=snapshot.ref, catalog_only=True, description=item.description))
    return result


def _merge_pi_rows(rows, snapshot):
    from agent_toolkit_tui.pi_extension_state import PiExtensionRow, PiCell
    locks, paths, _, _ = backing_modules("pi-extension")
    library = locks.read_lock(paths.library_lock_path()).skills
    result = list(rows)
    for item in snapshot.for_kind("pi-extension"):
        if item.source_type == "npm":
            identity = npm_identity(item.npm_source)
            existing = next((row for row in result if row.origin == "npm" and
                (row.npm_state.identity == identity if row.npm_state else row.slug in (identity, "npm:" + identity))), None)
            slug, warning = "npm:" + identity, ""
            if existing is not None and existing.npm_state is not None:
                for scope in ("global", "project"):
                    selected = existing.npm_state.for_scope(scope)
                    if (selected.configured or selected.installed) and (selected.source != item.npm_source or
                            selected.version not in (None, item.npm_source.rsplit("@", 1)[1])):
                        warning = "Native source/version differs from catalog; native state retained."
        else:
            slug, warning = catalog_target(library, item, snapshot.url)
            existing = next((row for row in result if row.slug == (slug or item.key)), None)
            if existing is not None and slug is None:
                warning = "Catalog identity conflicts with local/native content; existing content retained."
            slug = slug or item.key
        if existing is not None:
            result[result.index(existing)] = replace(existing, catalog_item=item,
                catalog_url=snapshot.url, catalog_ref=snapshot.ref,
                catalog_warning=warning, description=item.description)
            continue
        if warning:
            continue
        cell = PiCell(False, False, "catalog", managed=item.source_type == "git")
        result.append(PiExtensionRow(slug=slug, origin="catalog",
            source=item.npm_source if item.source_type == "npm" else item.source.url,
            global_cell=cell, project_cell=cell, managed=item.source_type == "git",
            catalog_item=item, catalog_url=snapshot.url, catalog_ref=snapshot.ref,
            catalog_only=True, description=item.description))
    return result
