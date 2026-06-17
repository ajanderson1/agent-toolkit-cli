"""Read/write `commands-lock.json`."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath, Path

CURRENT_VERSION = 1
SUPPORTED_VERSIONS = (1,)


def looks_like_sha(ref: str | None) -> bool:
    return ref is not None and re.fullmatch(r"[0-9a-f]{7,40}", ref) is not None


def is_sha_pinned(entry: "LockEntry") -> bool:
    return entry.source_type != "npm" and looks_like_sha(entry.ref)


@dataclass
class LockEntry:
    source: str
    source_type: str
    ref: str | None = None
    command_path: str | None = None
    upstream_sha: str | None = None
    local_sha: str | None = None
    parent_url: str | None = None
    read_only: bool = False
    extras: dict[str, object] = field(default_factory=dict)

    @property
    def ref_looks_pinned(self) -> bool:
        return is_sha_pinned(self)

    @property
    def ref_tracks_branch(self) -> bool:
        return self.source_type != "npm" and not looks_like_sha(self.ref)


@dataclass
class LockFile:
    version: int
    skills: dict[str, LockEntry]
    wrapper_extras: dict[str, object] = field(default_factory=dict)


_FIELDS = {"source", "sourceType", "ref", "commandPath", "upstreamSha", "localSha", "parentUrl", "readOnly"}


def validate_command_path(value: str | None) -> str | None:
    if value is None:
        return None
    p = PurePosixPath(value.replace("\\", "/"))
    if value.startswith(("/", "\\")) or p.is_absolute() or any(part in {"", ".", ".."} for part in p.parts):
        raise ValueError(f"unsafe commandPath: {value!r}")
    if p.name != "COMMAND.md":
        raise ValueError(f"commandPath must end in COMMAND.md: {value!r}")
    return str(p)


def _entry_from_dict(d: dict) -> LockEntry:
    extras = {k: v for k, v in d.items() if k not in _FIELDS}
    return LockEntry(
        source=d.get("source", ""),
        source_type=d.get("sourceType", ""),
        ref=d.get("ref"),
        command_path=validate_command_path(d.get("commandPath")),
        upstream_sha=d.get("upstreamSha"),
        local_sha=d.get("localSha"),
        parent_url=d.get("parentUrl"),
        read_only=bool(d.get("readOnly", False)),
        extras=extras,
    )


def _entry_to_dict(e: LockEntry) -> dict:
    out: dict[str, object] = {"source": e.source, "sourceType": e.source_type}
    if e.ref is not None:
        out["ref"] = e.ref
    if e.command_path is not None:
        out["commandPath"] = validate_command_path(e.command_path)
    if e.upstream_sha is not None:
        out["upstreamSha"] = e.upstream_sha
    if e.local_sha is not None:
        out["localSha"] = e.local_sha
    if e.parent_url is not None:
        out["parentUrl"] = e.parent_url
    if e.read_only:
        out["readOnly"] = True
    out.update(e.extras)
    return out


def read_lock(path: Path) -> LockFile:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return LockFile(version=CURRENT_VERSION, skills={})
    version = int(data.get("version", CURRENT_VERSION))
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"unsupported commands lock version: {version}")
    skills = {slug: _entry_from_dict(entry) for slug, entry in data.get("skills", {}).items()}
    extras = {k: v for k, v in data.items() if k not in {"version", "skills"}}
    return LockFile(version=version, skills=skills, wrapper_extras=extras)


def write_lock(path: Path, lock: LockFile) -> None:
    data: dict[str, object] = {"version": lock.version, "skills": {slug: _entry_to_dict(e) for slug, e in sorted(lock.skills.items())}}
    data.update(lock.wrapper_extras)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def add_entry(lock: LockFile, slug: str, entry: LockEntry) -> LockFile:
    skills = dict(lock.skills)
    skills[slug] = entry
    return LockFile(lock.version, skills, dict(lock.wrapper_extras))


def remove_entry(lock: LockFile, slug: str) -> LockFile:
    skills = dict(lock.skills)
    skills.pop(slug, None)
    return LockFile(lock.version, skills, dict(lock.wrapper_extras))


def clone_url_from_entry(e: LockEntry) -> str:
    url = e.extras.get("sourceUrl")
    if isinstance(url, str) and url:
        return url
    if e.source_type == "github" and "/" in e.source:
        return f"https://github.com/{e.source}.git"
    if e.source_type == "gitlab" and "/" in e.source:
        return f"https://gitlab.com/{e.source}.git"
    return e.source
