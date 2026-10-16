"""Canonical user-authored Instructions paths; installation needs no registry."""
from __future__ import annotations

from pathlib import Path


def library_root() -> Path:
    """Reserved Instructions library directory; inventory never creates it."""
    return Path.home() / '.agent-toolkit' / 'instructions'


def global_canonical_agents_md() -> Path:
    """User-owned canonical file, optionally a symlink to an external source."""
    return library_root().parent / 'AGENTS.md'


def project_canonical_agents_md(project_root: Path) -> Path:
    return project_root / 'AGENTS.md'
