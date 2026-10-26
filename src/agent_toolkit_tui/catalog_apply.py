"""Live batch revalidation before any catalogue-dependent acquisition."""
import click

from agent_toolkit_cli.asset_catalog_ops import (
    acquire_catalog_entry, backing_modules, catalog_target, resolve_catalog_entry,
    validate_targets,
)
from agent_toolkit_cli.skill_catalog import read_catalog


def snapshot_for(app, intents):
    if not intents:
        return None
    if hasattr(app, "_catalog_apply_snapshot"):
        return app._catalog_apply_snapshot
    return read_catalog()


def prepare_entry(kind, slug, *, intents, snapshot, targets, scope, home, project):
    selected = [value for key, value in intents.items() if key[0] == scope and key[-1] == slug]
    if not selected:
        return slug
    if snapshot is None or snapshot.error:
        raise ValueError("Catalog unavailable; refresh and retry")
    url, ref, expected = selected[0]
    identity = (url, ref, expected.key, expected.selector)
    if any((u, r, entry.key, entry.selector) != identity for u, r, entry in selected) or (url, ref) != (snapshot.url, snapshot.ref):
        raise ValueError("Catalog subscription changed; refresh and reselect")
    _, item = resolve_catalog_entry(kind, expected.key, expected=expected, snapshot=snapshot)
    validate_targets(item, tuple(sorted(targets)), scope=scope, home=home, project=project)
    locks, paths, _, _ = backing_modules(kind)
    actual, warning = catalog_target(locks.read_lock(paths.library_lock_path()).skills, item, snapshot.url)
    if warning or actual not in (None, slug):
        raise ValueError(warning or "Library slug changed; refresh and reselect")
    try:
        return acquire_catalog_entry(item, catalog_url=url, home=home)
    except click.ClickException as exc:
        raise ValueError(exc.format_message()) from exc
