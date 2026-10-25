"""Join live catalog identities to existing library records; explicit acquisition."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

import click

from agent_toolkit_cli.skill_catalog import CatalogSkill, CatalogSnapshot, read_catalog
from agent_toolkit_cli.skill_git import normalise_git_url
from agent_toolkit_cli.skill_lock import LockEntry, clone_url_from_entry, read_lock, write_lock
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path


def catalog_match(entry: LockEntry, item: CatalogSkill) -> bool:
    path = entry.skill_path or "SKILL.md"
    path = "." if path == "SKILL.md" else path
    return (
        normalise_git_url(clone_url_from_entry(entry)) == normalise_git_url(item.source.url)
        and path == item.source.subpath
        and entry.ref == item.source.ref
    )


def catalog_target(entries: dict[str, LockEntry], item: CatalogSkill, catalog_url: str) -> tuple[str | None, str]:
    """Resolve stable provenance before current selector equality. Never adopt changes."""
    associated = []
    for slug, entry in entries.items():
        provenance = entry.extras.get("catalog")
        if isinstance(provenance, dict) and provenance.get("url") == catalog_url and provenance.get("key") == item.key:
            associated.append(slug)
    matches = associated or [slug for slug, entry in entries.items() if catalog_match(entry, item)]
    if len(matches) > 1:
        return None, f"{item.key}: ambiguous matching library entries; inspect with CLI"
    if matches:
        slug = matches[0]
        if not catalog_match(entries[slug], item):
            return slug, f"{slug}: catalog selector changed; local source/ref/path retained. Inspect with skills status; source adoption is explicit CLI maintenance."
        return slug, ""
    if item.key in entries:
        return item.key, f"{item.key}: library source/ref/path conflicts with catalog; existing content retained"
    return None, ""


def resolve_catalog_skill(key: str, *, expected: CatalogSkill | None = None, home: Path | None = None) -> tuple[CatalogSnapshot, CatalogSkill]:
    snapshot = read_catalog(home=home)
    if snapshot is None or snapshot.error:
        raise ValueError(snapshot.error if snapshot else "no skill catalog subscription")
    item = next((s for s in snapshot.skills if s.key == key), None)
    if item is None:
        raise ValueError(f"{key}: no longer in the live catalog")
    if expected is not None and item.source != expected.source:
        raise ValueError(f"{key}: catalog source changed; refresh and reselect")
    return snapshot, item


def acquire_catalog_skill(item: CatalogSkill, *, catalog_url: str, home: Path | None = None) -> str:
    from agent_toolkit_cli.commands.skill import add
    lock_path = library_lock_path(home=home)
    lock = read_lock(lock_path)
    slug, warning = catalog_target(lock.skills, item, catalog_url)
    if warning:
        raise ValueError(warning)
    if slug is not None:
        if not (library_skill_path(slug, home=home) / "SKILL.md").is_file():
            raise ValueError(f"{slug}: recorded library content is missing; run skills doctor")
    else:
        slug = item.key
        if slug in lock.skills:
            raise ValueError(f"{slug}: library source/ref/path conflicts with catalog; existing content retained")
    # Reuse registration even for exact recorded matches: it verifies backing
    # ownership/ref without advancing it or discarding local work.
    try:
        with contextlib.redirect_stdout(io.StringIO()), click.Context(add) as ctx:
            ctx.invoke(add, source=item.source.url, source_option=None, slug=slug,
                       ref=item.source.ref, skill_name_flag=None, owned=False,
                       skill_path_flag=item.source.subpath)
    except click.ClickException as exc:
        raise ValueError(exc.format_message()) from exc
    # Re-read: registration may update sibling entries or encounter another writer.
    lock = read_lock(lock_path)
    if slug not in lock.skills or not catalog_match(lock.skills[slug], item):
        raise ValueError(f"{slug}: acquired source identity did not match catalog")
    lock.skills[slug].extras["catalog"] = {
        "url": catalog_url, "key": item.key,
        "source": item.source.url, "path": item.source.subpath, "ref": item.source.ref,
    }
    write_lock(lock_path, lock)
    return slug
