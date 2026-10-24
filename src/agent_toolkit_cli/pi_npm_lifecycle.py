"""Explicit installation/removal and legacy-record retirement for native npm.

No lifecycle operation writes a Toolkit npm registration. Binary installation
and inventory never call these functions implicitly.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from queue import Empty, Queue
from threading import Thread

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
        identity = None
    state = pi_npm.read_npm_states(home=home, project=project).get(identity) if identity else None
    if state:
        current = state.for_scope(scope)
        if current.configured or current.installed:
            return current.source
        other = state.project_scope if scope == "global" else state.global_scope
        return other.source
    if entry is not None and entry.source_type == "npm":
        raise PiSettingsError(f"{target}: retired Toolkit npm record; use an explicit npm: source or native identity; use migrate-npm-records to prune it")
    return None


def _run_pi(verb: str, source: str, *, scope: Scope, home: Path, project: Path | None) -> subprocess.CompletedProcess:
    pi_npm.ensure_scope_writable(scope=scope, home=home, project=project)
    executable = shutil.which("pi")
    if executable is None:
        raise PiSettingsError("native npm lifecycle requires installed Pi")
    if scope == "project" and project is None:
        raise PiSettingsError("project scope requires a project directory")
    home.mkdir(parents=True, exist_ok=True)
    try:
        return subprocess.run([executable, verb, source] + (["-l"] if scope == "project" else []),
            cwd=project or home, env={**os.environ, "HOME": str(home), "PI_CODING_AGENT_DIR": str(pi_npm.agent_dir(home))},
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


@contextmanager
def _external_settings_lock(path: Path):
    """Heartbeat with Pi's own lock library during potentially slow npm work."""
    native = pi_npm._pi_root(os.environ.get("AGENT_TOOLKIT_PI_PACKAGE"), shutil.which("pi"))
    node = shutil.which("node")
    if node is None:
        raise PiSettingsError("external removal requires Node.js for Pi's settings lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    process = None
    success = False
    try:
        process = subprocess.Popen([node, str(Path(__file__).parent / "data/pi_npm_lock.mjs"), str(native), str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ready = Queue()
        Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
        if ready.get(timeout=15) != "locked\n":
            _, diagnostic = process.communicate(timeout=10)
            raise PiSettingsError(diagnostic.strip() or "cannot acquire native settings lock")
        def check():
            if process.poll() is not None:
                raise PiSettingsError("native settings lock was lost; inspect Pi settings before retrying")
        yield check
        check()
        success = True
    except (OSError, Empty, subprocess.SubprocessError) as exc:
        raise PiSettingsError(f"native settings lock failed: {exc}") from exc
    finally:
        if process is not None:
            try:
                _, diagnostic = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate()
                if success:
                    raise PiSettingsError("native settings lock did not release cleanly")
            else:
                if success and process.returncode:
                    raise PiSettingsError(diagnostic.strip() or "native settings lock did not release cleanly")


def _drop_declaration_locked(identity: str, *, scope: Scope, home: Path, project: Path | None) -> None:
    """Caller must hold the selected native settings lock."""
    path = pi_npm.settings_path(scope=scope, home=home, project=project)
    data = _pi_settings._load(path)
    records, style = _pi_settings._package_sources(data, path)
    kept = [p for p in records if not (p["source"].startswith("npm:") and pi_npm._identity(p["source"]) == identity)]
    if len(kept) != len(records):
        data["packages"] = _pi_settings._encode_packages(kept, style)
        _write_settings(path, data)


@dataclass(frozen=True)
class NpmRemoval:
    identity: str
    scope: Scope
    declaration_removed: bool = False
    direct_removed: bool = False
    files_removed: bool = False
    files_remain: bool = False
    files_root: Path | None = None
    other_scope_configured: bool = False
    fallback_status: str | None = None
    remaining_root: Path | None = None
    remaining_status: str | None = None

    def describe(self) -> str:
        parts = []
        if self.declaration_removed:
            parts.append("removed Pi declaration")
        if self.direct_removed:
            parts.append("removed direct npm dependency record")
        if self.files_removed:
            parts.append("package files removed")
        elif self.files_remain:
            parts.append(f"package files remain at {self.files_root} (for example, as another package's dependency)")
        elif self.declaration_removed or self.direct_removed:
            parts.append("no scope-local package files were present")
        else:
            parts.append("no scoped native Pi declaration/direct installation found")
        if self.other_scope_configured:
            parts.append("other scope retains a native declaration")
        if self.fallback_status:
            parts.append(f"project now uses global default ({self.fallback_status})")
        elif self.remaining_root and self.remaining_root != self.files_root:
            parts.append(f"another installation remains ({self.remaining_status}) at {self.remaining_root}")
        return f"{self.identity} [{self.scope}]: " + "; ".join(parts)


def _remove_external(identity: str, state: pi_npm.NpmState, *, home: Path, project: Path | None) -> None:
    path = pi_npm.settings_path(scope="global", home=home)
    with _external_settings_lock(path) as check_lock:
        fresh = pi_npm.read_npm_states(home=home, project=project).get(identity)
        if fresh is None:
            return
        if fresh.snapshot_for("global") != state.snapshot_for("global"):
            raise PiSettingsError(f"{identity}: external target or native filters changed; refresh and confirm again")
        current = fresh.global_scope
        settings = _pi_settings._load(path)
        if settings.get("npmCommand") not in (None, ["npm"]):
            raise PiSettingsError("external removal requires the actual custom installer; not guessing an npm command")
        legacy, _ = pi_npm._legacy_npm(home, settings)
        if legacy is None or legacy.name != "node_modules" or current.root != legacy / identity:
            raise PiSettingsError("cannot establish the external npm installation prefix safely")
        if legacy.parent.name == "lib":
            prefix = legacy.parent.parent
        elif os.name == "nt":
            prefix = legacy.parent
        else:
            raise PiSettingsError("external root is not an npm global prefix; use its actual installer instead of guessing")
        npm = shutil.which("npm")
        if npm is None:
            raise PiSettingsError("npm is required to remove this external installation")
        check_lock()
        try:
            result = subprocess.run([npm, "uninstall", "--global", "--prefix", str(prefix), identity],
                cwd=home, capture_output=True, text=True, timeout=300, env={**os.environ, "HOME": str(home)})
        except (OSError, subprocess.SubprocessError) as exc:
            raise PiSettingsError(f"external npm removal failed: {exc}") from exc
        if result.returncode:
            raise PiSettingsError(result.stderr.strip() or result.stdout.strip() or "external npm removal failed")
        if current.root.exists() or current.root.is_symlink():
            raise PiSettingsError("external npm returned without removing the selected installation")
        check_lock()
        _drop_declaration_locked(identity, scope="global", home=home, project=project)


def remove_npm(*, identity: str, scope: Scope, home: Path, project: Path | None, external: bool = False) -> NpmRemoval:
    identity = pi_npm._identity(identity)
    pi_npm.ensure_scope_writable(scope=scope, home=home, project=project)
    state = pi_npm.read_npm_states(home=home, project=project).get(identity)
    base = pi_npm.agent_dir(home) if scope == "global" else project / ".pi"
    if state is None:
        root = base / "npm/node_modules" / identity
        remains = root.exists() or root.is_symlink()
        return NpmRemoval(identity, scope, files_remain=remains, files_root=root if remains else None)
    current = state.for_scope(scope)
    was_direct = identity in pi_npm._direct_names(base)
    if scope == "project" and current.record is None and not was_direct:
        raise PiSettingsError(f"{identity}: inherited global package; disable here instead of uninstalling a nonexistent project installation")
    if current.external and scope == "global":
        if not external:
            raise PiSettingsError(f"{identity}: installed by external npm at {current.root}; use --external with --yes to remove that shared installation")
        _remove_external(identity, state, home=home, project=project)
        was_direct = True
    else:
        record = current.record
        source = record if isinstance(record, str) else record["source"] if record else current.source
        result = _run_pi("uninstall", source, scope=scope, home=home, project=project)
        config = pi_npm.settings_path(scope=scope, home=home, project=project)
        remaining_records, _ = _pi_settings._package_sources(_pi_settings._load(config), config)
        declared = any(p["source"].startswith("npm:") and pi_npm._identity(p["source"]) == identity for p in remaining_records)
        still_direct = identity in pi_npm._direct_names(base)
        if result.returncode:
            diagnostic = result.stderr + result.stdout
            if not (result.returncode == 1 and record is None and "No matching package found" in diagnostic and not declared and not still_direct):
                raise PiSettingsError(diagnostic.strip() or "native Pi removal failed")
        if declared or still_direct:
            raise PiSettingsError(f"{identity}: native removal left a declaration or direct installation in {scope} scope")
    after = pi_npm.read_npm_states(home=home, project=project).get(identity)
    selected = after.for_scope(scope) if after else pi_npm.NpmScope()
    other = after.project_scope if scope == "global" and after else after.global_scope if after else pi_npm.NpmScope()
    root = current.scope_root
    remains = bool(root and (root.exists() or root.is_symlink()))
    return NpmRemoval(identity, scope, declaration_removed=current.record is not None and selected.record is None,
        direct_removed=was_direct, files_removed=root is not None and not remains,
        files_remain=remains, files_root=root, other_scope_configured=other.record is not None,
        fallback_status=selected.status if scope == "project" and selected.mode == "inherit" and selected.configured else None,
        remaining_root=selected.root, remaining_status=selected.status)


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
