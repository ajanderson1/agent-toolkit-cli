"""Read (PR1) Pi's per-scope settings.json packages[]/extensions[] arrays.

Verified against @earendil-works/pi-coding-agent@0.77.0:
  global  settings: ~/.pi/agent/settings.json
  project settings: <project>/.pi/settings.json
Both carry independent `packages` (registry refs) and `extensions`
(explicit local paths) arrays. PR1 reads only; the writer arrives in PR2.
Fails loud on malformed JSON rather than silently treating it as empty."""
from __future__ import annotations

import json
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
