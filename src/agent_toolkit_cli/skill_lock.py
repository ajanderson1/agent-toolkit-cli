"""Read/write `skills-lock.json` and `.skill-lock.json`.

Schema mirrors vercel-labs/skills/src/local-lock.ts plus our additive
`localSha` field. Unknown fields are preserved on round-trip via an
`extras` dict on each entry — guarantees forward compatibility with
upstream additions and with our own future fields.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CURRENT_VERSION = 1


@dataclass
class LockEntry:
    source: str
    source_type: str
    ref: str | None = None
    skill_path: str | None = None
    upstream_sha: str | None = None
    local_sha: str | None = None
    extras: dict[str, object] = field(default_factory=dict)


@dataclass
class LockFile:
    version: int
    skills: dict[str, LockEntry]


_KNOWN_FIELDS = {
    "source", "sourceType", "ref", "skillPath", "upstreamSha", "localSha",
}


def _entry_from_dict(d: dict) -> LockEntry:
    extras = {k: v for k, v in d.items() if k not in _KNOWN_FIELDS}
    return LockEntry(
        source=d.get("source", ""),
        source_type=d.get("sourceType", ""),
        ref=d.get("ref"),
        skill_path=d.get("skillPath"),
        upstream_sha=d.get("upstreamSha"),
        local_sha=d.get("localSha"),
        extras=extras,
    )


def _entry_to_dict(e: LockEntry) -> dict:
    out: dict[str, object] = {"source": e.source, "sourceType": e.source_type}
    if e.ref is not None:
        out["ref"] = e.ref
    if e.skill_path is not None:
        out["skillPath"] = e.skill_path
    if e.upstream_sha is not None:
        out["upstreamSha"] = e.upstream_sha
    if e.local_sha is not None:
        out["localSha"] = e.local_sha
    out.update(e.extras)
    return out


def read_lock(path: Path) -> LockFile:
    try:
        raw = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return LockFile(version=CURRENT_VERSION, skills={})
    if not isinstance(raw, dict) or raw.get("version") != CURRENT_VERSION:
        return LockFile(version=CURRENT_VERSION, skills={})
    skills_raw = raw.get("skills") or {}
    if not isinstance(skills_raw, dict):
        return LockFile(version=CURRENT_VERSION, skills={})
    skills = {
        name: _entry_from_dict(d)
        for name, d in skills_raw.items()
        if isinstance(d, dict)
    }
    return LockFile(version=CURRENT_VERSION, skills=skills)


def write_lock(path: Path, lock: LockFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_skills = {k: _entry_to_dict(lock.skills[k]) for k in sorted(lock.skills)}
    body = {"version": lock.version, "skills": sorted_skills}
    path.write_text(json.dumps(body, indent=2) + "\n")


def add_entry(lock: LockFile, slug: str, entry: LockEntry) -> LockFile:
    new_skills = dict(lock.skills)
    new_skills[slug] = entry
    return LockFile(version=lock.version, skills=new_skills)


def remove_entry(lock: LockFile, slug: str) -> LockFile:
    if slug not in lock.skills:
        return lock
    new_skills = {k: v for k, v in lock.skills.items() if k != slug}
    return LockFile(version=lock.version, skills=new_skills)
