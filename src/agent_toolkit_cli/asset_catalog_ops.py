"""Per-kind catalogue joins and guarded acquisition, not a universal installer."""
from __future__ import annotations

import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path, PurePosixPath

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_catalog import CatalogEntry, CatalogSnapshot, read_catalog, run_git


def backing_modules(kind):
    if kind == "agent":
        from agent_toolkit_cli import agent_lock as locks, agent_paths as paths
        return locks, paths, paths.library_agent_path, paths.canonical_agent_dir
    if kind == "command":
        from agent_toolkit_cli import command_lock as locks, command_paths as paths
        return locks, paths, paths.library_command_path, paths.canonical_command_dir
    if kind == "pi-extension":
        from agent_toolkit_cli import pi_extension_lock as locks, pi_extension_paths as paths
        return locks, paths, paths.library_pi_extension_path, paths.canonical_pi_extension_dir
    raise ValueError("unsupported catalogue acquisition kind")


def clone_url(kind, entry):
    if kind == "command":
        from agent_toolkit_cli.command_lock import clone_url_from_entry
    else:
        from agent_toolkit_cli.skill_lock import clone_url_from_entry
    return clone_url_from_entry(entry)


def entry_identity(kind, slug, entry):
    if entry.source_type == "npm":
        return None  # Obsolete npm lock entries never become catalogue candidates.
    if kind == "agent":
        relative = PurePosixPath(entry.agent_path or f"{slug}.md")
        path, filename = str(relative.parent), relative.name
    elif kind == "command":
        path, filename = str(PurePosixPath(entry.command_path or "COMMAND.md").parent), None
    else:
        path, filename = ".", None
    return kind, "git", skill_git.normalise_git_url(clone_url(kind, entry)), path, entry.ref, filename


def catalog_target(entries, item: CatalogEntry, catalog_url: str):
    associated = [slug for slug, entry in entries.items()
                  if isinstance(p := entry.extras.get("catalog"), dict)
                  and (p.get("url"), p.get("kind"), p.get("key")) == (catalog_url, item.kind, item.key)]
    matches = associated or [slug for slug, entry in entries.items() if entry_identity(item.kind, slug, entry) == item.selector]
    if len(matches) > 1:
        return None, f"{item.key}: ambiguous matching library entries; inspect with CLI"
    if matches:
        slug = matches[0]
        if entry_identity(item.kind, slug, entries[slug]) != item.selector:
            return slug, f"{slug}: catalog selector changed; local source/ref/path retained; inspect with CLI"
        return slug, ""
    if item.key in entries:
        return item.key, f"{item.key}: library source/ref/path conflicts with catalog; existing content retained"
    return None, ""


def resolve_catalog_entry(kind, key, *, expected=None, snapshot=None, home=None):
    snapshot = snapshot if snapshot is not None else read_catalog(home=home)
    if snapshot is None or snapshot.error:
        raise ValueError(snapshot.error if snapshot else "no shared catalog subscription")
    item = next((item for item in snapshot.for_kind(kind) if item.key == key), None)
    if item is None:
        raise ValueError(f"{key}: no longer in the live catalog")
    if expected is not None and item.selector != expected.selector:
        raise ValueError(f"{key}: catalog source/shape changed; refresh and reselect")
    return snapshot, item


def validate_pi_content(canonical):
    """Check local entrypoint shape without importing or executing extension code."""
    from agent_toolkit_cli.catalog_admission import _pi_entries, _regular_entry

    tree = {}
    for path in canonical.rglob("*"):
        relative = path.relative_to(canonical)
        if relative.parts[0] == ".git":
            continue
        tree[relative.as_posix()] = ("120000" if path.is_symlink() else
            "040000" if path.is_dir() else "100644" if path.is_file() else "unsupported")
    package = {}
    if "package.json" in tree:
        _regular_entry(tree, "package.json")
        package = json.loads((canonical / "package.json").read_text())
        if not isinstance(package, dict):
            raise ValueError("invalid Pi package.json")
    files = {name for name, mode in tree.items() if mode == "100644"}
    for relative in _pi_entries(files, package):
        _regular_entry(tree, relative)


def validate_backing(kind, slug, entry, *, scope="global", home=None, project=None):
    """Check actual content, origin, selection and containment without fetching."""
    locks, _, _, canonical_dir = backing_modules(kind)
    canonical = canonical_dir(slug, scope=scope, home=home, project=project)
    if not canonical.is_dir():
        raise ValueError(f"{slug}: recorded backing is missing; inspect with this kind\'s doctor command")
    root = Path(run_git(["rev-parse", "--show-toplevel"], cwd=canonical)).resolve()
    if not skill_git.remote_matches(root, clone_url(kind, entry), None):
        raise ValueError(f"{slug}: backing origin does not match recorded source")
    if entry.ref is not None and not skill_git._checked_out_at_ref(root, entry.ref, None):
        raise ValueError(f"{slug}: backing ref conflict; local content retained")
    identity = entry_identity(kind, slug, entry)
    directory = identity[3]
    expected = root / directory if entry.parent_url else root
    if canonical.resolve() != expected.resolve():
        raise ValueError(f"{slug}: canonical path conflicts with recorded backing")
    if not entry.parent_url and root != canonical.resolve():
        raise ValueError(f"{slug}: selected backing is not its own Git checkout")
    from agent_toolkit_cli.agent_paths import checked_agent_content, agent_content_path, validate_agent_revision
    if kind == "agent":
        agent_content_path(canonical, slug, entry)
        relative = entry.agent_path if entry.parent_url else Path(entry.agent_path or f"{slug}.md").name
        validate_agent_revision(root, "HEAD", {slug: relative})
    elif kind == "command":
        relative = entry.command_path if entry.parent_url else "COMMAND.md"
        checked_agent_content(root, relative or "COMMAND.md", slug)
    elif kind == "pi-extension":
        validate_pi_content(canonical)
    return canonical


def acquire_catalog_entry(item: CatalogEntry, *, catalog_url: str, home=None):
    if item.kind == "skill":
        from agent_toolkit_cli.skill_catalog_ops import acquire_catalog_skill
        return acquire_catalog_skill(item, catalog_url=catalog_url, home=home)
    if item.source_type != "git":
        raise ValueError("npm has no Toolkit library registration; use pi-extensions catalog install KEY --scope SCOPE")
    locks, paths, library_path, _ = backing_modules(item.kind)
    lock_path = paths.library_lock_path()
    lock = locks.read_lock(lock_path)
    slug, warning = catalog_target(lock.skills, item, catalog_url)
    if warning:
        raise ValueError(warning)
    if slug is not None:
        validate_backing(item.kind, slug, lock.skills[slug], home=home)
    else:
        slug = item.key
        canonical = library_path(slug)
        if canonical.exists() or canonical.is_symlink():
            raise ValueError(f"{slug}: unmanaged existing library content retained; inspect with CLI")
        assert item.source is not None
        parsed = replace(item.source, subpath=None if item.source.subpath == "." else item.source.subpath)
        with contextlib.redirect_stdout(io.StringIO()):
            if item.kind == "agent":
                from agent_toolkit_cli.commands.agent.add_cmd import _add_monorepo, _add_single
                if parsed.subpath:
                    _add_monorepo(parsed, slug, expected_entry_file=item.entry_file, refresh_existing_parent=False)
                else:
                    _add_single(parsed, slug, expected_entry_file=item.entry_file)
            elif item.kind == "command":
                from agent_toolkit_cli.commands.command.add_cmd import _add_monorepo, _add_single
                (_add_monorepo if parsed.subpath else _add_single)(parsed, slug)
            else:
                from agent_toolkit_cli.pi_extension_add import add
                add(source=parsed.url, slug=slug, parsed_source=parsed,
                    content_validator=validate_pi_content)
    lock = locks.read_lock(lock_path)
    if slug not in lock.skills or entry_identity(item.kind, slug, lock.skills[slug]) != item.selector:
        raise ValueError(f"{slug}: acquired source identity did not match catalog")
    validate_backing(item.kind, slug, lock.skills[slug], home=home)
    lock.skills[slug].extras["catalog"] = dict(url=catalog_url, kind=item.kind, key=item.key,
        source=item.source.url, path=item.source.subpath, ref=item.source.ref, entryFile=item.entry_file)
    locks.write_lock(lock_path, lock)
    return slug


def join_inventory(kind, rows, *, scope, home=None, project=None):
    """CLI inventory join; never turn catalogue presence into a local registration."""
    from agent_toolkit_cli.skill_catalog import npm_identity
    snapshot = read_catalog(home=home)
    if snapshot is None:
        return rows
    if snapshot.error:
        click.echo(f"Catalog warning: {snapshot.error}; catalog-only entries hidden", err=True)
        return rows
    locks, paths, _, _ = backing_modules(kind)
    library = locks.read_lock(paths.library_lock_path()).skills
    scoped = locks.read_lock(paths.lock_file_path(scope=scope, home=home, project=project)).skills
    result = [dict(row) for row in rows]
    for item in snapshot.for_kind(kind):
        if item.source_type == "npm":
            identity = npm_identity(item.npm_source)
            existing = next((row for row in result if row.get("origin") == "npm"
                and row["slug"] in (identity, "npm:" + identity)), None)
            slug, warning = "npm:" + identity, ""
            if existing is not None and existing["source"] != item.npm_source:
                warning = "Native source/version differs from catalog; native state retained"
        else:
            slug, warning = catalog_target(library, item, snapshot.url)
            existing = next((row for row in result if row["slug"] == (slug or item.key)), None)
            if existing is not None and slug is None:
                warning = "Catalog identity conflicts with local content; existing content retained"
            elif slug in scoped and entry_identity(kind, slug, scoped[slug]) != item.selector:
                warning = "Scoped backing conflicts with catalog; local content retained"
        if existing is not None:
            existing["catalog"] = item.as_dict()
            if warning:
                existing["catalogWarning"] = warning
            continue
        if warning:
            continue
        acquired = item.source_type == "git" and slug in library
        entry = library[slug] if acquired else None
        result.append(dict(slug=slug or item.key, kind=kind,
            source=entry.source if acquired else item.npm_source if item.source_type == "npm" else item.source.url,
            sourceType=entry.source_type if acquired else item.source_type,
            ref=entry.ref if acquired else item.source.ref if item.source else None,
            path=item.source.subpath if item.source else None, origin="library" if acquired else "catalog",
            scope="global" if acquired else scope, projected=False,
            harnesses=list(getattr(entry, "harnesses", ())) if acquired else [],
            upstream_sha=entry.upstream_sha if acquired else None, local_sha=entry.local_sha if acquired else None,
            managed=acquired, globalLoaded=False, projectLoaded=False,
            catalog=item.as_dict()))
    return result


def validate_targets(item, targets, *, scope, home, project):
    if item.source_type == "npm":
        raise ValueError("catalog enable does not install npm packages; use catalog install, then native enable")
    if not targets:
        raise ValueError("no harness targets selected")
    if item.kind == "agent":
        from agent_toolkit_cli.agent_adapters import get_adapter, UnsupportedMechanismError
        for target in targets:
            if item.entry_file == "AGENTS.md" and target != "pi":
                raise ValueError("complete-directory agents currently support Pi only")
            try:
                adapter = get_adapter(target)
            except UnsupportedMechanismError as exc:
                raise ValueError(f"unsupported agent target: {target}") from exc
            adapter.destination(item.key, scope=scope, home=home, project=project)
    elif item.kind == "command":
        from agent_toolkit_cli.command_adapters import get_adapter
        for target in targets:
            get_adapter(target).destination(item.key, scope=scope, home=home, project=project)
    elif targets != ("pi",):
        raise ValueError("Pi extensions support only Pi")


def enable_catalog_entry(item, *, catalog_url, targets, scope, home, project):
    validate_targets(item, targets, scope=scope, home=home, project=project)
    slug = acquire_catalog_entry(item, catalog_url=catalog_url, home=home)
    if item.kind == "pi-extension":
        from agent_toolkit_cli.pi_extension_ops import install
        install(slug=slug, scope=scope, home=home, project=project, git_only=True)
    else:
        from agent_toolkit_cli._install_core import InstallPlan
        if item.kind == "agent":
            from agent_toolkit_cli.agent_install import apply
        else:
            from agent_toolkit_cli.command_install import apply
        result = apply(InstallPlan(slug=slug, scope=scope, source=None, ref=None,
            add_agents=targets, remove_agents=()), home=home, project=project)
        if result.skipped:
            raise ValueError(f"{slug}: acquired, but targets were skipped: {', '.join(result.skipped)}")
    return slug


def install_catalog_npm(item, *, scope, home, project):
    if item.kind != "pi-extension" or item.source_type != "npm":
        raise ValueError("catalog install is only for native Pi npm packages; use catalog add/enable for Git")
    from agent_toolkit_cli.skill_catalog import npm_identity
    from agent_toolkit_cli.pi_npm import read_npm_states
    from agent_toolkit_cli.pi_npm_lifecycle import install_npm
    identity = npm_identity(item.npm_source)
    state = read_npm_states(home=home, project=project).get(identity)
    if state is not None:
        # Existing native state is authoritative. Never use catalogue install as upgrade/repair.
        selected = state.for_scope(scope)
        if selected.ambiguous or (selected.source and selected.source != item.npm_source):
            raise ValueError(f"{identity}: native source/version conflict; inspect Pi settings and use native maintenance")
        version = item.npm_source.rsplit("@", 1)[1]
        if ((selected.installed and selected.version != version)
                or (selected.scope_root is not None and selected.scope_version != version)):
            raise ValueError(f"{identity}: installed version conflicts with catalog; use native maintenance")
    install_npm(source=item.npm_source, scope=scope, home=home, project=project)
