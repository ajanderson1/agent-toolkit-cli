"""Backing selection and explicit, conservative migration on existing install seams."""
from __future__ import annotations

import dataclasses
import importlib
import shutil
import subprocess
from pathlib import Path

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli._paths_core import AssetTypeBinding, library_root_for_asset_type
from agent_toolkit_cli.behavior import project_backing


def _modules(binding):
    return (importlib.import_module(f"agent_toolkit_cli.{binding.asset_type}_paths"),
            importlib.import_module(f"agent_toolkit_cli.{binding.asset_type}_lock"))


def private_candidates(binding, slug, project):
    paths, _ = _modules(binding)
    candidates = [paths.project_store_root(project) / slug]
    if binding.asset_type == "skill":
        candidates.append(project / ".agents/skills" / slug)
    elif binding.asset_type == "agent":
        # Historical bug: agents and skills shared the skills backing namespace.
        from agent_toolkit_cli.skill_paths import project_store_root
        old = project_store_root(project) / slug
        if (old / f"{slug}.md").is_file() or (old / "AGENTS.md").is_file():
            candidates.append(old)
    return candidates


def resolve(binding: AssetTypeBinding, slug: str, project: Path, *, home=None) -> Path:
    from agent_toolkit_cli._paths_core import validate_asset_slug
    validate_asset_slug(slug)
    paths, locks = _modules(binding)
    entry = locks.read_lock(project / binding.lock_filename).skills.get(slug)
    central = library_root_for_asset_type(binding, home=home) / slug
    if entry is not None and entry.extras.get("projectBacking") == "central":
        return central
    candidates = private_candidates(binding, slug, project)
    found = [p for p in candidates if p.exists() or p.is_symlink()]
    if binding.asset_type == "skill" and candidates[0] in found:
        # An in-tree symlink is a projection, not another backing checkout.
        found = [p for p in found if p == candidates[0] or not p.is_symlink()]
    # Only recorded private installs are adopted; unknown paths are never overwritten.
    if found:
        distinct = {p.resolve() for p in found}
        # A normal in-tree projection may point to central or external private backing.
        if len(distinct) > 1:
            raise InstallError(f"{slug}: ambiguous private backing: {found}")
        if found[0].resolve() == central.resolve():
            return central
        return found[0]
    if entry is not None and entry.extras.get("projectBacking") != "central":
        # An old record with missing backing must NOT silently become a central install.
        return candidates[0]
    return candidates[0] if project_backing(home=home, creating=False) == "isolated" else central


def _validate_entry(entry, slug):
    if entry is None:
        return
    for value in (getattr(entry, "skill_path", None), getattr(entry, "agent_path", None), getattr(entry, "command_path", None)):
        if value is not None and (Path(value).is_absolute() or ".." in Path(value).parts or "\\" in value):
            raise InstallError(f"{slug}: malformed resource path {value!r}")


def check_creation(binding, slug, project, *, home=None):
    paths, locks = _modules(binding)
    canonical = resolve(binding, slug, project, home=home)
    central = library_root_for_asset_type(binding, home=home) / slug
    entry = locks.read_lock(project / binding.lock_filename).skills.get(slug)
    _validate_entry(entry, slug)
    if canonical != central and not (entry is not None and canonical.exists()):
        # Reads may describe disabled isolation, but every creation seam refuses it.
        project_backing(home=home)
        if canonical.exists() or canonical.is_symlink():
            raise InstallError(f"{slug}: unrecorded/foreign private backing at {canonical}")
    return canonical


def ensure(binding, slug, project, *, home=None, write_entry=True):
    paths, locks = _modules(binding)
    canonical = check_creation(binding, slug, project, home=home)
    lock_path = project / binding.lock_filename
    lock = locks.read_lock(lock_path)
    central = library_root_for_asset_type(binding, home=home) / slug
    if canonical.exists() and slug in lock.skills:
        return canonical
    if canonical != central and (canonical.exists() or canonical.is_symlink()):
        raise InstallError(f"{slug}: unrecorded/foreign private backing at {canonical}")
    global_entry = locks.read_lock(paths.library_lock_path()).skills.get(slug)
    _validate_entry(global_entry, slug)
    if global_entry is None:
        if binding.asset_type == "command" and canonical == central and central.exists():
            return central  # legacy manually seeded command, no provenance invented
        raise InstallError(f"{slug}: not in global library (no global lock entry); run `{binding.asset_type} add {slug}` first")
    if not central.exists():
        raise InstallError(f"{slug}: global canonical missing: {central}")
    if canonical != central and not canonical.exists():
        # Explicit enablement required even for engine/source callers and damaged old installs.
        if project_backing(home=home) != "isolated":
            raise InstallError(f"{slug}: private backing missing; restore it or explicitly migrate to central")
        canonical.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(central, canonical, symlinks=True)
    if write_entry and slug not in lock.skills:
        entry = dataclasses.replace(global_entry, upstream_sha=None, local_sha=None,
            extras={**global_entry.extras, "projectBacking": "central" if canonical == central else "isolated"})
        locks.write_lock(lock_path, locks.add_entry(lock, slug, entry))
    return canonical


def _git(path, *args):
    from agent_toolkit_cli import skill_git
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True,
                            text=True, env=skill_git._scrub(None))
    if result.returncode:
        raise InstallError(f"Cannot verify Git backing {path}: {result.stderr.strip()}")
    return result.stdout.strip()


def _tree(path):
    # Compare all resources, including ignored/untracked files; no .git internals.
    result = {}
    for item in path.rglob("*"):
        relative = item.relative_to(path)
        if ".git" in relative.parts:
            continue
        if item.is_symlink():
            result[str(relative)] = ("link", str(item.readlink()))
        elif item.is_file():
            result[str(relative)] = ("file", item.read_bytes(), item.stat().st_mode & 0o111)
    return result


def migrate(binding, slug, project):
    """Retarget only proven projections; retain old backing and all its history."""
    paths, locks = _modules(binding)
    lock_path = project / binding.lock_filename
    lock = locks.read_lock(lock_path)
    old_entry = lock.skills.get(slug)
    global_entry = locks.read_lock(paths.library_lock_path()).skills.get(slug)
    if old_entry is None or global_entry is None:
        raise InstallError(f"{slug}: migration requires both project and global lock entries")
    _validate_entry(old_entry, slug)
    _validate_entry(global_entry, slug)
    old = resolve(binding, slug, project)
    central = library_root_for_asset_type(binding) / slug
    if old == central:
        return old, central
    identity_fields = ("source", "source_type", "ref", "parent_url", f"{binding.asset_type}_path")
    if any(getattr(old_entry, key) != getattr(global_entry, key) for key in identity_fields):
        raise InstallError(f"{slug}: divergent source/ref/path lock identity")
    from agent_toolkit_cli import skill_git
    url = locks.clone_url_from_entry(global_entry)
    for path in (old, central):
        root = Path(_git(path.resolve(), "rev-parse", "--show-toplevel"))
        if _git(root, "status", "--porcelain", "--untracked-files=all"):
            raise InstallError(f"{slug}: dirty backing at {root}")
        if not skill_git.remote_matches(root, url, None):
            raise InstallError(f"{slug}: foreign origin at {root}")
    if _git(old.resolve(), "rev-parse", "HEAD") != _git(central.resolve(), "rev-parse", "HEAD") or _tree(old) != _tree(central):
        raise InstallError(f"{slug}: divergent backing; no files changed")
    links = []
    in_tree = (binding.asset_type == "skill" and old == project / ".agents/skills" / slug and not old.is_symlink())
    backup = old.with_name(f"{slug}.pre-central") if in_tree else None
    if backup is not None and (backup.exists() or backup.is_symlink()):
        raise InstallError(f"{slug}: preservation destination already exists: {backup}")
    if binding.asset_type == "skill":
        from agent_toolkit_cli.skill_agents import AGENTS
        from agent_toolkit_cli.skill_paths import agent_projection_dir
        destinations = {project / ".agents/skills" / slug}
        for name in AGENTS:
            try:
                destinations.add(agent_projection_dir(name, slug, scope="project", home=None, project=project))
            except ValueError:
                pass
    else:
        adapters = importlib.import_module(f"agent_toolkit_cli.{binding.asset_type}_adapters")
        from agent_toolkit_cli.skill_agents import AGENTS
        destinations = set()
        for name in ("standard", *AGENTS):
            try:
                adapter = adapters.get_adapter(name)
                dest = adapter.destination(slug, scope="project", home=None, project=project)
                destinations.add(dest)
                if binding.asset_type == "agent":
                    destinations.add(dest.with_suffix(""))
            except (ValueError, RuntimeError):
                continue
    for dest in destinations:
        if not dest.exists() and not dest.is_symlink():
            continue
        if in_tree and dest == old:
            continue  # rename the checkout intact, then replace only this slot
        if dest.is_symlink() and dest.resolve() == old.resolve():
            links.append((dest, central))
        elif dest.is_symlink() and binding.asset_type == "command" and dest.resolve() == (old / "COMMAND.md").resolve():
            links.append((dest, central / "COMMAND.md"))
        elif binding.asset_type == "skill" or dest.is_dir():
            raise InstallError(f"{slug}: foreign or in-tree projection at {dest}; preserve/restore it manually first")
        else:
            content = old / (f"{slug}.md" if binding.asset_type == "agent" else "COMMAND.md")
            if not content.is_file() or dest.read_bytes() != content.read_bytes():
                raise InstallError(f"{slug}: foreign/divergent projection at {dest}")
    changed = []
    moved = False
    try:
        if backup is not None:
            old.rename(backup)
            moved = True
            old.symlink_to(central, target_is_directory=True)
        for dest, desired in links:
            target = dest.readlink()
            changed.append((dest, target))
            dest.unlink()
            dest.symlink_to(desired, target_is_directory=desired.is_dir())
        entry = dataclasses.replace(old_entry, extras={**old_entry.extras, "projectBacking": "central"})
        locks.write_lock(lock_path, locks.add_entry(lock, slug, entry))
    except Exception:
        for dest, target in reversed(changed):
            dest.unlink(missing_ok=True)
            dest.symlink_to(target, target_is_directory=True)
        if moved:
            old.unlink(missing_ok=True)
            backup.rename(old)
        raise
    return backup or old, central
