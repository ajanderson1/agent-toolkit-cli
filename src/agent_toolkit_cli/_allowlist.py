"""Allow-list YAML read helpers and section routing.

The allow-list YAML at `~/.agent-toolkit.yaml` (user) or
`<project>/.agent-toolkit.yaml` (project) is a flat-section file mapping asset
kinds to lists of slugs. This module owns the kind ↔ section mapping and the
read path. The write path lives in `commands/_yaml_edit.py`.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Order matches the order sections appear when we materialise an empty file.
SECTIONS: tuple[str, ...] = (
    "skills",
    "agents",
    "commands",
    "hooks",
    "plugins",
    "mcps",
    "pi_extensions",
    "pi_packages",
)

_KIND_TO_SECTION: dict[str, str] = {
    "skill":         "skills",
    "agent":         "agents",
    "command":       "commands",
    "hook":          "hooks",
    "plugin":        "plugins",
    "mcp":           "mcps",
    "pi-extension":  "pi_extensions",
}

_SECTION_TO_KIND: dict[str, str] = {v: k for k, v in _KIND_TO_SECTION.items()}


def kind_to_section(kind: str) -> str:
    """Map an asset kind to its allow-list section name.

    Raises ValueError for any unknown kind.
    """
    if kind not in _KIND_TO_SECTION:
        raise ValueError(f"unknown asset kind: {kind!r}")
    return _KIND_TO_SECTION[kind]


def section_to_kind(section: str) -> str:
    """Inverse of `kind_to_section`. Raises ValueError on unknown sections."""
    if section not in _SECTION_TO_KIND:
        raise ValueError(f"unknown allow-list section: {section!r}")
    return _SECTION_TO_KIND[section]


def read_allowlist(path: Path) -> dict[str, list[str]]:
    """Parse `path` into a section→slugs dict.

    Missing file, empty file, and missing sections all yield empty lists.
    Unknown sections in the file are silently ignored.
    """
    out: dict[str, list[str]] = {s: [] for s in SECTIONS}
    if not path.exists():
        return out
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return out
    # TODO(task-4): decide error policy for malformed YAML — currently the
    # yaml.YAMLError propagates uncaught; the bash consumer can choose to
    # catch and surface as a friendly CLI error, or this module can wrap.
    parsed = yaml.safe_load(text) or {}
    if not isinstance(parsed, dict):
        return out
    for section in SECTIONS:
        value = parsed.get(section) or []
        if isinstance(value, list):
            out[section] = [str(s) for s in value if s]
    return out
