"""Instructions asset-type lockfile model — own dataclass, own read/write.

Differs deliberately from skill_lock.LockEntry: an instructions entry has no
`source`/`ref`/`upstream_sha` because the asset type has no upstream repo. Sharing
LockEntry would mean every other field is meaningless for instructions; a
separate file is honest about shape.

On-disk shape (v1):

    {
      "version": 1,
      "instructions": {
        "<slug>": {
          "scope": "project" | "global",
          "source": "AGENTS.md",
          "harnesses": ["claude-code", "gemini-cli", ...]
        }
      }
    }

`slug` is always the source filename for now (we manage one AGENTS.md per
lockfile per scope). Keyed-by-slug shape is forward-compatible with future
multi-file support.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

SUPPORTED_VERSIONS: tuple[int, ...] = (1,)

Scope = Literal["project", "global"]


@dataclass
class InstructionsLockEntry:
    scope: Scope
    source: str          # relative to scope root, e.g. "AGENTS.md"
    harnesses: list[str] = field(default_factory=list)


@dataclass
class InstructionsLockFile:
    version: int
    instructions: dict[str, InstructionsLockEntry]


def read_lock(path: Path) -> InstructionsLockFile:
    """Read a lock file. Missing file → empty lock."""
    if not path.exists():
        return InstructionsLockFile(version=1, instructions={})
    raw = json.loads(path.read_text())
    version = int(raw.get("version", 1))
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"unsupported instructions-lock version: {version} (supported: {SUPPORTED_VERSIONS})"
        )
    entries: dict[str, InstructionsLockEntry] = {}
    for slug, d in raw.get("instructions", {}).items():
        entries[slug] = InstructionsLockEntry(
            scope=d["scope"],
            source=d["source"],
            harnesses=list(d.get("harnesses", [])),
        )
    return InstructionsLockFile(version=version, instructions=entries)


def write_lock(path: Path, lock: InstructionsLockFile) -> None:
    """Write a lock file. Creates parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": lock.version,
        "instructions": {
            slug: {
                "scope": entry.scope,
                "source": entry.source,
                "harnesses": list(entry.harnesses),
            }
            for slug, entry in lock.instructions.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def add_entry(
    lock: InstructionsLockFile, slug: str, entry: InstructionsLockEntry
) -> InstructionsLockFile:
    """Return a new lock with `slug` set to `entry`. Original untouched."""
    new_entries = dict(lock.instructions)
    new_entries[slug] = entry
    return replace(lock, instructions=new_entries)


def remove_entry(lock: InstructionsLockFile, slug: str) -> InstructionsLockFile:
    """Return a new lock without `slug`. No-op if absent."""
    if slug not in lock.instructions:
        return lock
    new_entries = {k: v for k, v in lock.instructions.items() if k != slug}
    return replace(lock, instructions=new_entries)
