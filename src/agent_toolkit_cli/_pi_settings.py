"""Pi per-scope settings.json reader (PR1) and packages[] writer (PR2).

Verified against @earendil-works/pi-coding-agent@0.77.0:
  global  settings: ~/.pi/agent/settings.json
  project settings: <project>/.pi/settings.json
Both carry independent `packages` (registry refs) and `extensions`
(explicit local paths) arrays. PR1 reads only; PR2 adds add_package /
remove_package. Fails loud on malformed JSON rather than silently treating
it as empty. Writer is atomic (temp + os.replace) and preserves every key
it does not own."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

Scope = Literal["project", "global"]

_GLOBAL_SETTINGS = (".pi", "agent", "settings.json")
_PROJECT_SETTINGS = (".pi", "settings.json")


class PiSettingsError(RuntimeError):
    """Pi settings.json could not be parsed."""


def settings_path(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    if scope == "global":
        if home is None:
            raise ValueError("global scope requires home")
        return home.joinpath(*_GLOBAL_SETTINGS)
    if project is None:
        raise ValueError("project scope requires project")
    return project.joinpath(*_PROJECT_SETTINGS)


def _load(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise PiSettingsError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PiSettingsError(f"{path}: top-level value is not an object")
    return data


def _string_list(data: dict[str, object], key: str, path: Path) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PiSettingsError(f"{path}: `{key}` is not a list of strings")
    return value


def read_packages(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> list[str]:
    path = settings_path(scope=scope, home=home, project=project)
    return _string_list(_load(path), "packages", path)


def read_extension_paths(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> list[str]:
    path = settings_path(scope=scope, home=home, project=project)
    return _string_list(_load(path), "extensions", path)


# ---------------------------------------------------------------------------
# PR2 writer: add_package / remove_package
# ---------------------------------------------------------------------------


def _write_atomic(path: Path, data: dict[str, object]) -> None:
    """Atomically write `data` as 2-space-indented JSON + trailing newline.

    Uses a temp sibling + os.replace so a crash mid-write never truncates the
    user's real Pi config (same posture as skill_lock.write_lock)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2) + "\n"
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def add_package(
    spec: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> None:
    """Add `spec` to the per-scope settings.json packages[] (idempotent).

    Preserves every other key. Creates the file (and the packages key) only
    when needed. Raises PiSettingsError without touching the file if the
    existing settings.json is unparseable."""
    path = settings_path(scope=scope, home=home, project=project)
    data = _load(path)  # {} if missing; raises PiSettingsError on malformed/non-dict
    packages = _string_list(data, "packages", path)  # raises if present & not list[str]
    if spec in packages:
        return
    data["packages"] = [*packages, spec]
    _write_atomic(path, data)


def remove_package(
    spec: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> None:
    """Remove `spec` from packages[]. No-op if absent or file missing.

    Preserves every other key. Raises PiSettingsError on malformed existing
    settings.json."""
    path = settings_path(scope=scope, home=home, project=project)
    if not path.exists():
        return
    data = _load(path)
    packages = _string_list(data, "packages", path)
    if spec not in packages:
        return
    data["packages"] = [p for p in packages if p != spec]
    _write_atomic(path, data)
