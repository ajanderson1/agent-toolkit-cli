"""Explicit installation/removal and legacy-record retirement for native npm.

No lifecycle operation writes a Toolkit npm registration. Binary installation
and inventory never call these functions implicitly.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from agent_toolkit_cli import _pi_settings, pi_npm
from agent_toolkit_cli._pi_settings import PiSettingsError, Scope
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_cli.pi_extension_paths import library_lock_path, lock_file_path
from agent_toolkit_cli.pi_local_extensions import _settings_lock, _write_settings


def npm_source_for(target: str, *, scope: Scope, home: Path, project: Path | None) -> str | None:
    """Resolve an explicit npm source/native identity; Git slug wins collisions."""
    if target.startswith("npm:"):
        pi_npm._identity(target)
        return target
    entry = read_lock(library_lock_path(env={})).skills.get(target)
    if entry is not None and entry.source_type != "npm":
        return None
    try:
        identity = pi_npm._identity(target)
    except PiSettingsError:
        return None
    state = pi_npm.read_npm_states(home=home, project=project).get(identity)
    if state:
        current = state.for_scope(scope)
        if current.configured or current.installed:
            return current.source
        other = state.project_scope if scope == "global" else state.global_scope
        return other.source
    if entry is not None and entry.source_type == "npm":
        # Explicit old-script install requests may still name their old source;
        # this is never used for inventory, permissions or automatic migration.
        return entry.source if entry.source.startswith("npm:") else "npm:" + entry.source
    return None


def _run_pi(verb: str, source: str, *, scope: Scope, home: Path, project: Path | None) -> subprocess.CompletedProcess:
    executable = shutil.which("pi")
    if executable is None:
        raise PiSettingsError("native npm lifecycle requires installed Pi")
    if scope == "project" and project is None:
        raise PiSettingsError("project scope requires a project directory")
    home.mkdir(parents=True, exist_ok=True)
    try:
        return subprocess.run([executable, verb, source] + (["-l"] if scope == "project" else []),
            cwd=project or home, env={**os.environ, "HOME": str(home), "PI_CODING_AGENT_DIR": str(home / ".pi/agent")},
            capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise PiSettingsError(f"native Pi {verb} failed: {exc}") from exc


def install_npm(*, source: str, scope: Scope, home: Path, project: Path | None) -> None:
    if not source.startswith("npm:"):
        raise PiSettingsError("native npm install requires an npm: source")
    identity = pi_npm._identity(source)
    result = _run_pi("install", source, scope=scope, home=home, project=project)
    if result.returncode:
        raise PiSettingsError(result.stderr.strip() or result.stdout.strip() or "native Pi install failed")
    state = pi_npm.read_npm_states(home=home, project=project).get(identity)
    if state is None or state.for_scope(scope).record is None or not state.for_scope(scope).scope_compatible:
        raise PiSettingsError(f"{identity}: native install returned without a compatible scoped installation/declaration")


def _drop_declaration(identity: str, *, scope: Scope, home: Path, project: Path | None) -> None:
    path = _pi_settings.settings_path(scope=scope, home=home, project=project)
    with _settings_lock(path):
        data = _pi_settings._load(path)
        records, style = _pi_settings._package_sources(data, path)
        kept = [p for p in records if not (p["source"].startswith("npm:") and pi_npm._identity(p["source"]) == identity)]
        if len(kept) != len(records):
            data["packages"] = _pi_settings._encode_packages(kept, style)
            _write_settings(path, data)


def remove_npm(*, identity: str, scope: Scope, home: Path, project: Path | None, external: bool = False) -> None:
    identity = pi_npm._identity(identity)
    state = pi_npm.read_npm_states(home=home, project=project).get(identity)
    if state is None:
        return
    current = state.for_scope(scope)
    base = home / ".pi/agent" if scope == "global" else project / ".pi"
    if scope == "project" and current.record is None and identity not in pi_npm._direct_names(base):
        raise PiSettingsError(f"{identity}: inherited global package; disable here instead of uninstalling a nonexistent project installation")
    if current.external and scope == "global":
        if not external:
            raise PiSettingsError(f"{identity}: installed by external npm at {current.root}; use --external with --yes to remove that shared installation")
        settings = _pi_settings._load(_pi_settings.settings_path(scope="global", home=home))
        if settings.get("npmCommand") not in (None, ["npm"]):
            raise PiSettingsError("external removal requires the actual custom installer; not guessing an npm command")
        legacy, _ = pi_npm._legacy_npm(home, settings)
        if legacy is None or legacy.name != "node_modules" or current.root != legacy / identity:
            raise PiSettingsError("cannot establish the external npm installation prefix safely")
        prefix = legacy.parent.parent if legacy.parent.name == "lib" else legacy.parent
        npm = shutil.which("npm")
        if npm is None:
            raise PiSettingsError("npm is required to remove this external installation")
        try:
            result = subprocess.run([npm, "uninstall", "--global", "--prefix", str(prefix), identity],
                cwd=home, capture_output=True, text=True, timeout=300, env={**os.environ, "HOME": str(home)})
        except (OSError, subprocess.SubprocessError) as exc:
            raise PiSettingsError(f"external npm removal failed: {exc}") from exc
        if result.returncode:
            raise PiSettingsError(result.stderr.strip() or result.stdout.strip() or "external npm removal failed")
        if current.root.exists():
            raise PiSettingsError("external npm returned without removing the selected installation")
        _drop_declaration(identity, scope=scope, home=home, project=project)
        return
    record = current.record
    source = record if isinstance(record, str) else record["source"] if record else current.source
    result = _run_pi("uninstall", source, scope=scope, home=home, project=project)
    remaining_records = _pi_settings.read_package_records(scope=scope, home=home, project=project)
    declared = any(p["source"].startswith("npm:") and pi_npm._identity(p["source"]) == identity for p in remaining_records)
    still_direct = identity in pi_npm._direct_names(base)
    if result.returncode:
        diagnostic = result.stderr + result.stdout
        if not (result.returncode == 1 and record is None and "No matching package found" in diagnostic and not declared and not still_direct):
            raise PiSettingsError(diagnostic.strip() or "native Pi removal failed")
    if declared or still_direct:
        raise PiSettingsError(f"{identity}: native removal left a declaration or direct installation in {scope} scope")


def migrate_npm_records(*, scope: Scope, home: Path, project: Path | None, apply: bool = False) -> dict:
    """Backup/prune only old npm registrations. Never install or activate anything."""
    path = lock_file_path(scope=scope, home=home, project=project)
    if not path.exists():
        return {"path": str(path), "retired": [], "applied": False}
    with _settings_lock(path):
        before = path.read_bytes()
        data = _pi_settings._load(path)
        entries = data.get("skills", {})
        if not isinstance(entries, dict):
            raise PiSettingsError(f"{path}: invalid Toolkit lock entries")
        retired = [slug for slug, entry in entries.items() if isinstance(entry, dict) and entry.get("sourceType") == "npm"]
        report = {"path": str(path), "retired": retired, "applied": False}
        if apply and retired:
            backup = path.with_name(path.stem + ".before-native-npm-" + hashlib.sha256(before).hexdigest()[:12] + ".json")
            if not backup.exists():
                fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(before)
                    stream.flush(); os.fsync(stream.fileno())
            elif backup.read_bytes() != before:
                raise PiSettingsError(f"{backup}: refusing to overwrite a different backup")
            data["skills"] = {slug: entry for slug, entry in entries.items() if slug not in retired}
            _write_settings(path, data)
            report.update(applied=True, backup=str(backup))
        return report
