"""Native Pi npm facts and controls; no Toolkit npm installation registry.

The packaged Node bridge resolves resources offline using installed Pi. Discovery
never installs or imports extension code. Missing native support is explicit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from agent_toolkit_cli import _pi_settings
from agent_toolkit_cli._pi_settings import PiSettingsError, Scope


@dataclass(frozen=True)
class NpmScope:
    record: dict | str | None = None
    source: str = ""
    root: Path | None = None
    version: str | None = None
    metadata: dict | None = None
    compatible: bool = False
    configured: bool = False
    missing: bool = False
    mode: str = "available"
    entries: tuple[tuple[Path, bool], ...] = ()
    resources: tuple[Path, ...] = ()
    external: bool = False
    scope_root: Path | None = None
    scope_version: str | None = None
    scope_compatible: bool = False
    ambiguous: bool = False
    settings_destination: Path | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.entries) and all(enabled for _, enabled in self.entries)

    @property
    def mixed(self) -> bool:
        return any(enabled for _, enabled in self.entries) and not self.enabled

    @property
    def installed(self) -> bool:
        return self.root is not None and self.version is not None

    @property
    def status(self) -> str:
        if self.ambiguous:
            return "Ambiguous"
        if self.missing:
            return "Needs repair" if self.installed else "Missing"
        if not self.configured:
            return "Available" if self.installed else "Not installed"
        if not self.resources:
            return "No extensions"
        return "Mixed" if self.mixed else "Enabled" if self.enabled else "Disabled"

    def summary(self) -> dict:
        return {"status": self.status, "mode": self.mode, "installed": self.installed,
            "configured": self.configured, "version": self.version,
            "root": str(self.root) if self.root else None, "source": self.source,
            "mixed": self.mixed, "external": self.external,
            "scopeRoot": str(self.scope_root) if self.scope_root else None,
            "scopeVersion": self.scope_version, "ambiguous": self.ambiguous,
            "entrypoints": [{"path": str(path), "enabled": enabled} for path, enabled in self.entries]}


@dataclass(frozen=True)
class NpmState:
    identity: str
    global_scope: NpmScope = field(default_factory=NpmScope)
    project_scope: NpmScope = field(default_factory=NpmScope)
    snapshot: str = ""

    def for_scope(self, scope: str) -> NpmScope:
        return self.global_scope if scope == "global" else self.project_scope

    def snapshot_for(self, scope: str) -> str:
        """Bind scoped intent without invalidating it on our other-scope Apply.

        Project all/none is explicit policy, independent of the global enabled
        bit. Global source/version/path changes still invalidate its targets.
        """
        current = self.for_scope(scope)
        record = {"source": current.record} if isinstance(current.record, str) else current.record
        relevant = {key: record[key] for key in ("source", "autoload", "extensions") if key in record} if record is not None else None
        value = {"record": relevant, "source": current.source, "mode": current.mode,
            "root": current.root, "version": current.version, "metadata": current.metadata,
            "compatible": current.compatible, "resources": current.resources,
            "entries": [path for path, _ in current.entries],
            "scope_root": current.scope_root, "scope_version": current.scope_version,
            "ambiguous": current.ambiguous, "settings_destination": current.settings_destination}
        if scope == "project" and (current.mode in ("inherit", "override") or record and record.get("autoload") is False):
            base = self.global_scope.record
            value["global_base"] = base if isinstance(base, str) else base.get("source") if base else None
        return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def agent_dir(home: Path) -> Path:
    """Honor Pi's user override; an explicitly different HOME stays isolated."""
    override = os.environ.get("PI_CODING_AGENT_DIR") if home == Path.home() else None
    return Path(override).expanduser().absolute() if override else home / ".pi/agent"


def settings_path(*, scope: Scope, home: Path, project: Path | None = None) -> Path:
    if scope == "global":
        return agent_dir(home) / "settings.json"
    if scope != "project" or project is None:
        raise PiSettingsError("scope must be global or project; project scope requires a project directory")
    return project / ".pi/settings.json"


def _settings_destination(path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:
        raise PiSettingsError(f"cannot resolve settings pointer: {exc}") from exc


def ensure_scope_writable(*, scope: Scope, home: Path, project: Path | None) -> Path:
    path = settings_path(scope=scope, home=home, project=project)
    if project is not None:
        try:
            if settings_path(scope="global", home=home).resolve() == settings_path(scope="project", home=home, project=project).resolve():
                raise PiSettingsError("global and project settings share one file; a scoped change would also change the other scope")
        except (OSError, RuntimeError) as exc:
            if isinstance(exc, PiSettingsError):
                raise
            raise PiSettingsError(f"cannot establish settings scope isolation: {exc}") from exc
    return path


def _identity(source: str) -> str:
    name = _pi_settings.npm_identity(source)
    if not re.fullmatch(r"(?:@[A-Za-z0-9._~\-]+/)?[A-Za-z0-9_~][A-Za-z0-9._~\-]*", name):
        raise PiSettingsError(f"invalid npm package identity: {name!r}")
    return name


def _json_object(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _pi_root(override: str | None, executable: str | None) -> Path:
    candidates = [Path(override)] if override else []
    if executable:
        candidates.extend(Path(executable).resolve().parents)
    for path in candidates:
        if (_json_object(path / "package.json").get("name") == "@earendil-works/pi-coding-agent"
                and (path / "dist/core/package-manager.js").is_file()):
            return path
    raise PiSettingsError("native npm controls require installed Pi (set AGENT_TOOLKIT_PI_PACKAGE for a nonstandard installation)")


def _system_global_npm(npm: str | None, home: str, prefix: str | None) -> tuple[str | None, tuple[str, ...]]:
    if npm is None:
        return None, ()
    try:
        # Explicit system binary, never a command read from project settings.
        env = {**os.environ, "HOME": home, "NPM_CONFIG_OFFLINE": "true",
            "NPM_CONFIG_IGNORE_SCRIPTS": "true", "NPM_CONFIG_UPDATE_NOTIFIER": "false", "NPM_CONFIG_LOGS_MAX": "0"}
        root = subprocess.run([npm, "root", "-g"], cwd=home, capture_output=True, text=True, env=env, timeout=10, check=True).stdout.strip()
        result = subprocess.run([npm, "ls", "-g", "--depth=0", "--json"], cwd=home, capture_output=True, text=True, env=env, timeout=10)
        dependencies = json.loads(result.stdout).get("dependencies", {})
        return root, tuple(dependencies) if isinstance(dependencies, dict) else ()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, ()


def _legacy_npm(home: Path, settings: dict) -> tuple[Path | None, tuple[str, ...]]:
    override = os.environ.get("AGENT_TOOLKIT_NPM_GLOBAL_ROOT")
    if override:
        root = Path(override)
        names = []
        if root.is_dir():
            for path in root.iterdir():
                if path.name.startswith("@") and path.is_dir():
                    names.extend(f"{path.name}/{child.name}" for child in path.iterdir() if child.is_dir())
                elif path.is_dir() and not path.name.startswith("."):
                    names.append(path.name)
        return root, tuple(names)
    if settings.get("npmCommand") not in (None, ["npm"]):
        return None, ()  # Never guess an external root for a custom installer.
    root, names = _system_global_npm(shutil.which("npm"), str(home), os.environ.get("NPM_CONFIG_PREFIX"))
    return Path(root) if root else None, names


def _direct_sources(base: Path) -> dict[str, str]:
    dependencies = _json_object(base / "npm/package.json").get("dependencies", {})
    sources = {}
    if isinstance(dependencies, dict):
        for name, version in dependencies.items():
            name = _identity(name)
            if not isinstance(version, str):
                raise PiSettingsError(f"{base}: invalid npm dependency specification for {name}")
            if version.startswith("file:"):
                location = Path(version[5:])
                if not location.is_absolute():
                    version = "file:" + os.path.abspath(base / "npm" / location)
            sources[name] = f"npm:{name}@{version}"
    return sources


def _direct_names(base: Path) -> set[str]:
    return set(_direct_sources(base))


def _has_extensions(root: Path) -> bool:
    data = _json_object(root / "package.json")
    pi = data.get("pi")
    return bool(isinstance(pi, dict) and pi.get("extensions")) or (root / "extensions").is_dir()


def _scope_from_json(value: dict | None) -> NpmScope:
    if value is None:
        return NpmScope()
    return NpmScope(**{**value,
        "root": Path(value["root"]) if value.get("root") else None,
        "scope_root": Path(value["scope_root"]) if value.get("scope_root") else None,
        "settings_destination": Path(value["settings_destination"]) if value.get("settings_destination") else None,
        "entries": tuple((Path(e["path"]), bool(e["enabled"])) for e in value["entries"]),
        "resources": tuple(Path(p) for p in value["resources"]),
    })


def read_npm_states(
    *, home: Path, project: Path | None, overrides: dict[str, dict] | None = None,
) -> dict[str, NpmState]:
    """Union direct installations and configured npm sources, resolved offline."""
    bases = {"global": agent_dir(home)}
    if project is not None:
        bases["project"] = project / ".pi"
    settings = {}
    identities = set()
    candidates = {}
    locations = {}
    for scope, base in bases.items():
        path = settings_path(scope=scope, home=home, project=project)
        locations[scope] = _settings_destination(path)
        data = overrides[scope] if overrides and scope in overrides else _pi_settings._load(path)
        records, _ = _pi_settings._package_sources(data, path)
        identities.update(_identity(p["source"]) for p in records if p["source"].startswith("npm:"))
        # Native manager receives resource selection only, not executable commands.
        settings[scope] = {key: data[key] for key in ("packages", "extensions") if key in data}
        candidates[scope] = _direct_sources(base)
        identities.update(name for name in candidates[scope] if _has_extensions(base / "npm/node_modules" / name))
    global_data = _pi_settings._load(settings_path(scope="global", home=home))
    legacy_root, legacy_names = _legacy_npm(home, global_data)
    if legacy_root:
        for name in legacy_names:
            if not _has_extensions(legacy_root / name):
                continue
            name = _identity(name)
            identities.add(name)
            root = legacy_root / name
            version = _json_object(root / "package.json").get("version")
            source = f"npm:{name}@file:{root.resolve()}" if root.is_symlink() else f"npm:{name}@{version}" if isinstance(version, str) else f"npm:{name}"
            candidates["global"].setdefault(name, source)
    if not identities:
        return {}
    native_root = _pi_root(os.environ.get("AGENT_TOOLKIT_PI_PACKAGE"), shutil.which("pi"))
    node = shutil.which("node")
    if node is None:
        raise PiSettingsError("native npm controls require Node.js (Pi's runtime)")
    request = {"home": str(home), "project": str(project) if project else None,
        "agentDir": str(bases["global"]), "piRoot": str(native_root),
        "global": settings["global"], "projectSettings": settings.get("project", {}),
        "identities": sorted(identities), "candidates": candidates,
        "legacyRoot": str(legacy_root) if legacy_root else None}
    try:
        result = subprocess.run([node, str(Path(__file__).parent / "data/pi_npm_bridge.mjs")],
            input=json.dumps(request), text=True, capture_output=True, timeout=30,
            env={**os.environ, "HOME": str(home), "PI_CODING_AGENT_DIR": str(bases["global"]), "PI_OFFLINE": "1"})
        if result.returncode:
            raise PiSettingsError(result.stderr.strip() or "native Pi inventory failed")
        values = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise PiSettingsError(f"native Pi inventory failed: {exc}") from exc
    for scope, destination in locations.items():
        if destination != _settings_destination(settings_path(scope=scope, home=home, project=project)):
            raise PiSettingsError("settings pointer changed during inventory; refresh and retry")
    states = {}
    for name, value in values.items():
        for scope, destination in locations.items():
            value[scope]["settings_destination"] = str(destination)
        snapshot = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        states[name] = NpmState(name, _scope_from_json(value["global"]), _scope_from_json(value["project"]), snapshot)
    return states


def _change_selection(
    *, identity: str, scope: Scope, home: Path, project: Path | None,
    enabled: bool | None, expected_snapshot: str | None = None,
) -> None:
    from agent_toolkit_cli.pi_local_extensions import _settings_lock, _write_settings

    identity = _identity(identity)
    path = ensure_scope_writable(scope=scope, home=home, project=project)
    try:
        with _settings_lock(path):
            state = read_npm_states(home=home, project=project).get(identity)
            if state is None:
                raise PiSettingsError(f"{identity}: no native installation or declaration; install first")
            if expected_snapshot is not None and expected_snapshot not in (state.snapshot, state.snapshot_for(scope)):
                raise PiSettingsError(f"{identity}: native package or filters changed; revert, refresh and queue again")
            current = state.for_scope(scope)
            if current.ambiguous:
                raise PiSettingsError(f"{identity}: multiple native declarations are ambiguous; resolve them in Pi settings before changing selection")
            if enabled is True and (not current.compatible or not current.resources):
                raise PiSettingsError(f"{identity}: install or repair this scope before enabling; toggle does not download packages")
            data = _pi_settings._load(path)
            records, style = _pi_settings._package_sources(data, path)
            index = next((i for i, p in enumerate(records) if p["source"].startswith("npm:") and _identity(p["source"]) == identity), None)
            if index is None:
                if enabled is None or not current.configured and not enabled:
                    return  # Reset/disable must not activate an unconfigured package's other resources.
                if scope == "project" and state.global_scope.configured:
                    record = {"source": state.global_scope.source, "autoload": False}
                else:
                    # A checkbox activates extensions only. A newly declared
                    # package must not also activate its bundled resource kinds.
                    record = {"source": current.source, "skills": [], "prompts": [], "themes": []}
                index = len(records)
                records.append(record)
            record = dict(records[index])
            delta = record.get("autoload") is False
            if enabled is None:
                record.pop("extensions", None)
                if delta and scope == "project" and current.mode in ("inherit", "override") and set(record) <= {"source", "autoload"}:
                    records.pop(index)
                else:
                    records[index] = record
            else:
                if delta:
                    # Basename globs cover both ordinary and dot-prefixed names,
                    # including future package entrypoints. [] in an inherited
                    # autoload:false delta would mean INHERIT, not disable.
                    record["extensions"] = ["*", ".*"] if enabled else ["!*", "!.*"]
                elif enabled:
                    record.pop("extensions", None)
                else:
                    record["extensions"] = []
                records[index] = record
            data["packages"] = _pi_settings._encode_packages(records, style)
            prospective = read_npm_states(home=home, project=project, overrides={scope: data}).get(identity)
            if enabled is not None:
                target = prospective.for_scope(scope) if prospective else NpmScope()
                if target.enabled != enabled or target.mixed:
                    raise PiSettingsError(f"{identity}: conflicting native reference prevents this selection; inspect Pi config")
            _write_settings(path, data)
    except (OSError, ValueError) as exc:
        raise PiSettingsError(f"{path}: {exc}") from exc


def set_npm_enabled(
    *, identity: str, enabled: bool, scope: Scope, home: Path,
    project: Path | None, expected_snapshot: str | None = None,
) -> None:
    """Settings-only all/none selection; never installs or deletes package files."""
    _change_selection(identity=identity, enabled=enabled, scope=scope, home=home,
        project=project, expected_snapshot=expected_snapshot)


def reset_npm_override(
    *, identity: str, scope: Scope, home: Path, project: Path | None,
    expected_snapshot: str | None = None,
) -> None:
    """Reset extension policy only, keeping owned installs and other deltas."""
    _change_selection(identity=identity, enabled=None, scope=scope, home=home, project=project, expected_snapshot=expected_snapshot)
