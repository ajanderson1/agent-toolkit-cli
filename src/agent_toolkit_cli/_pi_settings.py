"""Read/write helpers for `~/.pi/agent/settings.json`.

The toolkit treats this file as a JSON document with a `packages: [str]`
field. Read returns the list; write helpers (commit 2) preserve unknown keys.
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
