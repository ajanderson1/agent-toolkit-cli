"""Native Pi npm facts and controls; no Toolkit npm installation registry.

The packaged Node bridge resolves resources offline using installed Pi. Discovery
never installs or imports extension code. Missing native support is explicit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
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

    @property
    def enabled(self) -> bool:
        return bool(self.entries) and all(enabled for _, enabled in self.entries)

    @property
    def mixed(self) -> bool:
        return any(enabled for _, enabled in self.entries) and not self.enabled

    @property
    def installed(self) -> bool:
        return self.root is not None and self.version is not None


@dataclass(frozen=True)
class NpmState:
    identity: str
    global_scope: NpmScope = field(default_factory=NpmScope)
    project_scope: NpmScope = field(default_factory=NpmScope)
    snapshot: str = ""

    def for_scope(self, scope: str) -> NpmScope:
        return self.global_scope if scope == "global" else self.project_scope


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


@lru_cache(maxsize=8)
def _pi_root(override: str | None, executable: str | None) -> Path:
    candidates = [Path(override)] if override else []
    if executable:
        candidates.extend(Path(executable).resolve().parents)
    for path in candidates:
        if (_json_object(path / "package.json").get("name") == "@earendil-works/pi-coding-agent"
                and (path / "dist/core/package-manager.js").is_file()):
            return path
    raise PiSettingsError("native npm controls require installed Pi (set AGENT_TOOLKIT_PI_PACKAGE for a nonstandard installation)")


@lru_cache(maxsize=8)
def _system_global_npm(npm: str | None, home: str, prefix: str | None) -> tuple[str | None, tuple[str, ...]]:
    if npm is None:
        return None, ()
    try:
        # Explicit system binary, never a command read from project settings.
        env = {**os.environ, "HOME": home}
        root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, env=env, timeout=10, check=True).stdout.strip()
        result = subprocess.run([npm, "ls", "-g", "--depth=0", "--json"], capture_output=True, text=True, env=env, timeout=10)
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


def _direct_names(base: Path) -> set[str]:
    dependencies = _json_object(base / "npm/package.json").get("dependencies", {})
    return {_identity(name) for name in dependencies} if isinstance(dependencies, dict) else set()


def _has_extensions(root: Path) -> bool:
    data = _json_object(root / "package.json")
    pi = data.get("pi")
    return bool(isinstance(pi, dict) and pi.get("extensions")) or (root / "extensions").is_dir()


def _scope_from_json(value: dict | None) -> NpmScope:
    if value is None:
        return NpmScope()
    return NpmScope(**{**value,
        "root": Path(value["root"]) if value.get("root") else None,
        "entries": tuple((Path(e["path"]), bool(e["enabled"])) for e in value["entries"]),
        "resources": tuple(Path(p) for p in value["resources"]),
    })


def read_npm_states(
    *, home: Path, project: Path | None, overrides: dict[str, dict] | None = None,
) -> dict[str, NpmState]:
    """Union direct installations and configured npm sources, resolved offline."""
    bases = {"global": home / ".pi/agent"}
    if project is not None:
        bases["project"] = project / ".pi"
    settings = {}
    identities = set()
    for scope, base in bases.items():
        path = _pi_settings.settings_path(scope=scope, home=home, project=project)
        data = overrides[scope] if overrides and scope in overrides else _pi_settings._load(path)
        records, _ = _pi_settings._package_sources(data, path)
        identities.update(_identity(p["source"]) for p in records if p["source"].startswith("npm:"))
        # Native manager receives resource selection only, not executable commands.
        settings[scope] = {key: data[key] for key in ("packages", "extensions") if key in data}
        identities.update(name for name in _direct_names(base) if _has_extensions(base / "npm/node_modules" / name))
    global_data = _pi_settings._load(_pi_settings.settings_path(scope="global", home=home))
    legacy_root, legacy_names = _legacy_npm(home, global_data)
    if legacy_root:
        identities.update(_identity(name) for name in legacy_names if _has_extensions(legacy_root / name))
    if not identities:
        return {}
    native_root = _pi_root(os.environ.get("AGENT_TOOLKIT_PI_PACKAGE"), shutil.which("pi"))
    node = shutil.which("node")
    if node is None:
        raise PiSettingsError("native npm controls require Node.js (Pi's runtime)")
    request = {"home": str(home), "project": str(project) if project else None,
        "agentDir": str(bases["global"]), "piRoot": str(native_root),
        "global": settings["global"], "projectSettings": settings.get("project", {}),
        "identities": sorted(identities), "legacyRoot": str(legacy_root) if legacy_root else None}
    try:
        result = subprocess.run([node, str(Path(__file__).parent / "data/pi_npm_bridge.mjs")],
            input=json.dumps(request), text=True, capture_output=True, timeout=30,
            env={**os.environ, "HOME": str(home), "PI_CODING_AGENT_DIR": str(bases["global"]), "PI_OFFLINE": "1"})
        if result.returncode:
            raise PiSettingsError(result.stderr.strip() or "native Pi inventory failed")
        values = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise PiSettingsError(f"native Pi inventory failed: {exc}") from exc
    states = {}
    for name, value in values.items():
        snapshot = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        states[name] = NpmState(name, _scope_from_json(value["global"]), _scope_from_json(value["project"]), snapshot)
    return states
