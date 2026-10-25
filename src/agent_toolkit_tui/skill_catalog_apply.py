"""Prepare frozen skill selections; acquisitions never imply successful exposure."""
from dataclasses import dataclass
from pathlib import Path

from agent_toolkit_cli import skill_catalog_ops as ops
from agent_toolkit_cli.skill_catalog import read_catalog
from agent_toolkit_cli.skill_collections import catalog, projection
from agent_toolkit_cli.skill_install import InstallError, _current_linked_agents, validate_projection_context
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, library_lock_path, lock_file_path
from agent_toolkit_tui.skill_state import SkillIntent

SkillKey = tuple[str, str, str]


@dataclass
class CatalogPreparation:
    blocked: set[SkillKey]
    acquired: tuple[str, ...]
    errors: tuple[str, ...]


def prepare_catalog_acquisitions(
    pending: dict[SkillKey, str], intents: dict[SkillKey, SkillIntent], *, home: Path, project: Path | None,
) -> CatalogPreparation:
    """Validate each collection before acquisition; never write projections here."""
    units: dict[tuple[str, str, str | None], list[SkillKey]] = {}
    for key, intent in intents.items():
        if key in pending:
            units.setdefault((key[0], *intent.identity[:2]), []).append(key)
    needs_catalog = any(intents[k].catalog_item is not None for keys in units.values() for k in keys)
    snapshot = read_catalog(home=home) if needs_catalog else None
    blocked: set[SkillKey] = set()
    acquired: list[str] = []
    errors: list[str] = []
    for (scope, repository, ref), keys in units.items():
        selected_project = project if scope == 'project' else None
        try:
            library = read_lock(library_lock_path(home=home)).skills
            records = {**library, **read_lock(lock_file_path(scope=scope, home=home, project=selected_project)).skills}
            # Legacy containers can supply proven children not individually locked yet.
            groups = catalog(scope=scope, home=home, project=selected_project)
            derived = {n: c for group in groups for n,c in group.children.items()}
            containers = {n for group in groups for n in (*group.containers, *group.container_conflicts, group.wrapper) if n is not None}
            entries = {n:c.entry for n,c in derived.items()}
            entries.update(records)
            selected_items = {}
            for key in keys:
                intent = intents[key]
                entry = entries.get(key[2])
                if entry is not None and ops.skill_identity(entry) != intent.identity:
                    raise ValueError(f'{key[2]}: local identity changed; refresh and reselect')
                if intent.catalog_item is not None:
                    if snapshot is None or snapshot.error:
                        raise ValueError('Catalog unavailable; refresh and retry')
                    if (snapshot.url, snapshot.ref) != (intent.catalog_url, intent.catalog_ref):
                        raise ValueError('Catalog subscription changed; refresh and reselect')
                    _, item = ops.resolve_catalog_skill(intent.catalog_item.key, expected=intent.catalog_item, home=home, snapshot=snapshot)
                    actual, warning = ops.catalog_target(library, item, snapshot.url)
                    if warning or (actual is not None and actual != key[2]):
                        raise ValueError(warning or 'Library slug changed; refresh and reselect')
                    selected_items[key[2]] = item
                elif entry is None:
                    raise ValueError(f'{key[2]}: local record disappeared; refresh and reselect')
                validate_projection_context(slug=key[2], target_agents=(key[1],), scope=scope, home=home, project=selected_project)
                path = projection(key[2], key[1], scope=scope, home=home, project=selected_project)
                canonical = canonical_skill_dir(key[2], scope=scope, home=home, project=selected_project)
                targets = {canonical.resolve()}
                if key[2] in derived:
                    targets.add(derived[key[2]].path.resolve())
                if path.exists() or path.is_symlink():
                    if not path.is_symlink() or path.resolve() not in targets:
                        raise ValueError(f'{key[2]}: conflicting projection at {path}; local content retained')
            known = {ops.skill_identity(e) for n,e in entries.items() if n not in containers and ops.skill_identity(e)[:2] == (repository, ref)}
            known.update(member for key in keys for member in intents[key].members)
            # Only relevant catalogue metadata is needed to prevent unsafe real-root exposure.
            if snapshot is not None and not snapshot.error:
                known.update(ops.catalog_identity(i) for i in snapshot.skills if ops.catalog_identity(i)[:2] == (repository, ref))
            for agent in {k[1] for k in keys}:
                selected = {ops.skill_identity(e) for slug,e in entries.items()
                            if slug not in containers and ops.skill_identity(e)[:2] == (repository, ref)
                            and agent in _current_linked_agents(slug=slug, scope=scope, home=home, project=selected_project)}
                for key in keys:
                    if key[1] == agent:
                        if pending[key] == 'link': selected.add(intents[key].identity)
                        else: selected.discard(intents[key].identity)
                if (repository, ref, '.') in selected and not known <= selected:
                    raise ValueError('Cannot prove independent nested isolation while the real root is selected; unselect the root first')
            for slug, item in sorted(selected_items.items()):
                actual = ops.acquire_catalog_skill(item, catalog_url=snapshot.url, home=home)
                acquired.append(actual)
                if actual != slug:
                    raise ValueError('Library slug changed; refresh and reselect')
        except (ValueError, RuntimeError, OSError, InstallError) as exc:
            blocked.update(keys)
            errors.append(f'{repository} @ {ref or "default"}: {exc}')
    return CatalogPreparation(blocked, tuple(dict.fromkeys(acquired)), tuple(errors))
