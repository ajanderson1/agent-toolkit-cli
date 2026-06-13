"""mcps-lock.json — records tool-owned MCP projections per (slug, harness).

Global scope: ~/.agent-toolkit/mcps-lock.json. Project scope: <project>/mcps-lock.json.
Each slug maps to a list of McpLockEntry (one per harness it is installed into).
Mirrors agent_lock.py's filename-per-kind convention (plural, like agents-lock.json).

Lock-model decision (2026-06-10, #329 critical review): the record stays
INDEPENDENT of skill_lock.LockEntry — a per-harness projection list per slug
genuinely does not fit LockEntry's one-canonical-path-per-slug shape — but is
ALIGNED for future composability: versioned envelope ({"version": 1, "mcps": ...})
and entries are plain objects so the bundle composite's grouping field
(see docs/solutions/architecture-patterns/clone-and-project-substrate-for-
bundle-plugin-capability-2026-06-10.md) can be added without a migration.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agent_toolkit_cli.mcp_adapters import atomic_write_text

LOCK_FILENAME = "mcps-lock.json"
LOCK_VERSION = 1


@dataclass(frozen=True)
class McpLockEntry:
    slug: str
    harness: str
    source: str            # provenance: the entry's install_method ("npx"|"uvx"|"docker"|"url"|"local")
    pin: str | None = None  # version transparency: resolved version at install time, None = floating


def lock_path_for_scope(scope: str, *, home: Path, project: Path | None) -> Path:
    if scope == "global":
        return home / ".agent-toolkit" / LOCK_FILENAME
    if project is None:
        raise ValueError("project scope requires a project root")
    return project / LOCK_FILENAME


def read_lock(path: Path) -> dict[str, list[McpLockEntry]]:
    if not path.is_file():
        return {}
    # A malformed lock raises rather than silently returning {} — fail-loud per
    # convention (a corrupt lock must surface, not silently drop tracked
    # projections). This is a deliberate divergence from skill_lock.read_lock,
    # which fails soft; do NOT "fix" it to match.
    raw = json.loads(path.read_text(encoding="utf-8") or "{}")
    out: dict[str, list[McpLockEntry]] = {}
    for slug, entries in raw.get("mcps", {}).items():
        # Tolerant read: ignore unknown per-entry keys (future grouping field).
        out[slug] = [
            McpLockEntry(
                slug=slug, harness=e["harness"], source=e["source"],
                pin=e.get("pin"),
            )
            for e in entries
        ]
    return out


def write_lock(path: Path, lock: dict[str, list[McpLockEntry]]) -> None:
    serialisable = {
        "version": LOCK_VERSION,
        "mcps": {
            slug: [
                {"harness": e.harness, "source": e.source,
                 **({"pin": e.pin} if e.pin else {})}
                for e in sorted(entries, key=lambda x: x.harness)
            ]
            for slug, entries in sorted(lock.items())
        },
    }
    atomic_write_text(path, json.dumps(serialisable, indent=2) + "\n")


def upsert_entry(lock: dict[str, list[McpLockEntry]], entry: McpLockEntry) -> dict[str, list[McpLockEntry]]:
    out = {k: list(v) for k, v in lock.items()}
    existing = [e for e in out.get(entry.slug, []) if e.harness != entry.harness]
    existing.append(entry)
    out[entry.slug] = existing
    return out


def remove_entry(lock: dict[str, list[McpLockEntry]], *, slug: str, harness: str) -> dict[str, list[McpLockEntry]]:
    out = {k: list(v) for k, v in lock.items()}
    if slug in out:
        out[slug] = [e for e in out[slug] if e.harness != harness]
        if not out[slug]:
            del out[slug]
    return out
