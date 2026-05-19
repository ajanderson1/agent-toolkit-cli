"""Read/write helpers for `~/.pi/agent/settings.json`.

The toolkit treats this file as a JSON document with a `packages: [str]`
field. Read returns the list; write helpers (commit 3) preserve unknown keys.
This is the third-party-channel sibling of `_yaml_edit.py` (which owns the
allowlist YAML for the first-party channel).
"""
from __future__ import annotations

import json
from pathlib import Path


def read_packages(path: Path) -> list[str]:
    """Return the `packages[]` list from a Pi settings.json file.

    Missing file or empty file -> []. Missing `packages` key -> []. Malformed
    JSON raises ValueError with a friendly message — the toolkit fails loudly
    rather than silently swallowing a corrupt settings.json.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed settings.json at {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        return []
    packages = parsed.get("packages") or []
    if not isinstance(packages, list):
        return []
    return [str(p) for p in packages if p]


def write_packages(path: Path, packages: list[str]) -> None:
    """Write `packages` as the `packages[]` field, preserving other keys.

    Creates parent dirs and file if missing. The on-disk representation is
    `{"packages": [...], ...other-keys}`. We deliberately preserve any keys
    other than `packages` so Pi-internal settings survive toolkit edits.
    Malformed existing JSON raises ValueError mentioning the path.
    """
    parsed: dict
    if path.exists() and path.read_text(encoding="utf-8").strip():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed settings.json at {path}: {exc}") from exc
        if not isinstance(parsed, dict):
            parsed = {}
    else:
        parsed = {}

    parsed["packages"] = list(packages)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")


def add_package(path: Path, source: str) -> None:
    """Add SOURCE to `packages[]` (idempotent; creates file if missing)."""
    current = read_packages(path)
    if source in current:
        return
    write_packages(path, current + [source])


def remove_package(path: Path, source: str) -> None:
    """Remove SOURCE from `packages[]` (idempotent; no-op if missing)."""
    current = read_packages(path)
    if source not in current:
        return
    write_packages(path, [s for s in current if s != source])


def read_extensions_overrides(path: Path) -> list[str]:
    """Return `extensions[]` from settings.json (override-pattern list).

    Schema-tolerant: missing file -> [], missing key -> [], non-list -> [].
    Raises ValueError on malformed JSON, mentioning the path.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed settings.json at {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        return []
    extensions = parsed.get("extensions") or []
    if not isinstance(extensions, list):
        return []
    return [str(e) for e in extensions if e]
