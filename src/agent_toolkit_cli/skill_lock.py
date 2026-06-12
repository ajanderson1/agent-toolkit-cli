"""Read/write `skills-lock.json` and `.skill-lock.json`.

Supports two on-disk versions of `vercel-labs/skills`'s lock format:

  * **v1** — the project lock (`./skills-lock.json` in `local-lock.ts`).
    Minimal, timestamp-free, designed for clean diffs. This is the format
    we write when creating a new lock file.

  * **v3** — the global lock (`~/.agents/.skill-lock.json` in
    `skill-lock.ts`). Adds `sourceUrl`, `skillFolderHash` (replacing our
    `upstreamSha`), `installedAt`/`updatedAt` timestamps, and a wrapper
    `dismissed` / `lastSelectedAgents` block.

The reader transparently accepts both. The writer preserves whichever
version the existing file was — never downgrade an existing file in place,
because `npx skills` reading it later would reject a mismatched version.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

CURRENT_VERSION = 1
SUPPORTED_VERSIONS: tuple[int, ...] = (1, 3)


def looks_like_sha(ref: str | None) -> bool:
    """True when `ref` can only sensibly be a commit SHA (lowercase hex,
    7-40 chars — git's abbreviated-to-full range).

    Why a heuristic is safe both ways: `git clone --branch` rejects a 40-hex
    *branch name* anyway, so classifying one as a SHA is strictly more correct;
    and a short all-hex *tag* classified as a SHA still resolves — fetch_ref +
    checkout accept tag names too. (Moved verbatim from pi_extension_add, #345.)
    """
    return bool(ref) and re.fullmatch(r"[0-9a-f]{7,40}", ref) is not None


def is_sha_pinned(entry: "LockEntry") -> bool:
    """True when the entry's `ref` is a user SHA-pin: a SHA-shaped ref on a
    store-owned (git-cloned) entry. An npm entry carrying a hex `ref`
    (hand-edited / future-schema) is NOT a pin — gating on source_type
    preserves the #386 phantom-pin fix. `upstream_sha` is NEVER consulted:
    it is the observed tip at add time, not a pin (#330 review)."""
    return entry.source_type != "npm" and looks_like_sha(entry.ref)


@dataclass
class LockEntry:
    source: str
    source_type: str
    ref: str | None = None
    skill_path: str | None = None
    agent_path: str | None = None
    pi_extension_path: str | None = None
    upstream_sha: str | None = None
    local_sha: str | None = None
    parent_url: str | None = None
    read_only: bool = False
    extras: dict[str, object] = field(default_factory=dict)

    @property
    def ref_looks_pinned(self) -> bool:
        """Derived: does `ref` read as a user SHA-pin? Never a persisted
        field — the lock format is the vercel-labs/skills interop format and
        we do not add fields to it (#345)."""
        return is_sha_pinned(self)

    @property
    def ref_tracks_branch(self) -> bool:
        """Derived: does this store-owned entry follow a moving branch/tag
        (or the remote default when ref is None) rather than a fixed SHA?
        npm entries track nothing here (no clone)."""
        return self.source_type != "npm" and not looks_like_sha(self.ref)


@dataclass
class LockFile:
    version: int
    skills: dict[str, LockEntry]
    wrapper_extras: dict[str, object] = field(default_factory=dict)


# v1 entry field names; v3 entry adds sourceUrl, skillFolderHash,
# installedAt, updatedAt (and lacks upstreamSha/localSha/ref).
_V1_ENTRY_FIELDS = {
    "source", "sourceType", "ref", "skillPath", "agentPath", "piExtensionPath",
    "upstreamSha", "localSha", "parentUrl", "readOnly",
}
_V3_ENTRY_FIELDS = {
    "source", "sourceType", "sourceUrl", "ref", "skillPath", "agentPath",
    "piExtensionPath", "skillFolderHash", "installedAt", "updatedAt", "pluginName",
    "parentUrl", "readOnly",
}
# Wrapper-level fields v3 carries outside `skills`.
_V3_WRAPPER_FIELDS = {"dismissed", "lastSelectedAgents"}


def _entry_from_dict_v1(d: dict) -> LockEntry:
    extras = {k: v for k, v in d.items() if k not in _V1_ENTRY_FIELDS}
    return LockEntry(
        source=d.get("source", ""),
        source_type=d.get("sourceType", ""),
        ref=d.get("ref"),
        skill_path=d.get("skillPath"),
        agent_path=d.get("agentPath"),
        pi_extension_path=d.get("piExtensionPath"),
        upstream_sha=d.get("upstreamSha"),
        local_sha=d.get("localSha"),
        parent_url=d.get("parentUrl"),
        read_only=bool(d.get("readOnly", False)),
        extras=extras,
    )


def _entry_from_dict_v3(d: dict) -> LockEntry:
    extras = {k: v for k, v in d.items() if k not in _V3_ENTRY_FIELDS}
    return LockEntry(
        source=d.get("source", ""),
        source_type=d.get("sourceType", ""),
        ref=d.get("ref"),
        skill_path=d.get("skillPath"),
        agent_path=d.get("agentPath"),
        pi_extension_path=d.get("piExtensionPath"),
        # v3 uses skillFolderHash for the upstream pin.
        upstream_sha=d.get("skillFolderHash"),
        # v3 has no local_sha concept; leave None.
        local_sha=None,
        parent_url=d.get("parentUrl"),
        read_only=bool(d.get("readOnly", False)),
        extras={
            **extras,
            # Preserve v3-only metadata so round-trip is lossless.
            **({"sourceUrl": d["sourceUrl"]} if "sourceUrl" in d else {}),
            **({"installedAt": d["installedAt"]} if "installedAt" in d else {}),
            **({"updatedAt": d["updatedAt"]} if "updatedAt" in d else {}),
            **({"pluginName": d["pluginName"]} if "pluginName" in d else {}),
        },
    )


def _entry_to_dict_v1(e: LockEntry) -> dict:
    out: dict[str, object] = {"source": e.source, "sourceType": e.source_type}
    if e.ref is not None:
        out["ref"] = e.ref
    if e.skill_path is not None:
        out["skillPath"] = e.skill_path
    if e.agent_path is not None:
        out["agentPath"] = e.agent_path
    if e.pi_extension_path is not None:
        out["piExtensionPath"] = e.pi_extension_path
    if e.upstream_sha is not None:
        out["upstreamSha"] = e.upstream_sha
    if e.local_sha is not None:
        out["localSha"] = e.local_sha
    if e.parent_url is not None:
        out["parentUrl"] = e.parent_url
    if e.read_only:
        out["readOnly"] = True
    # Drop v3-only keys we may have stashed in extras when round-tripping
    # from a v3 file we later wrote as v1 (e.g. a project lock copied from
    # the global one — unusual, but be tidy).
    for k, v in e.extras.items():
        if k in {"sourceUrl", "installedAt", "updatedAt", "skillFolderHash",
                 "pluginName"}:
            continue
        out[k] = v
    return out


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def _apply_insteadof(url: str) -> str:
    """Rewrite `url` per the user's git `url.<base>.insteadOf` config.

    A fresh SSH-only host that synced a library from another machine has no
    HTTPS credential helper; the canonical fix git documents for that setup is
    ``url."git@github.com:".insteadOf = "https://github.com/"``. git applies
    this natively at clone time, but we apply it here too so the resolved URL
    is explicit and unit-testable, and so SSH-only hosts clone github/gitlab
    sources over their working (SSH) transport instead of a doomed HTTPS one
    (#251).

    Reads git config read-only with a scrubbed env; any failure (no git, no
    config) leaves the URL unchanged. When several bases match, the one whose
    rewrite value is the longest wins — git's own precedence rule.
    """
    try:
        proc = subprocess.run(
            ["git", "config", "--get-regexp", r"^url\..*\.insteadof$"],
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            capture_output=True,
            text=True,
        )
    except (OSError, ValueError):
        return url
    if proc.returncode != 0 or not proc.stdout:
        return url

    best_rewrite = ""
    best_base = ""
    for line in proc.stdout.splitlines():
        key, _, rewrite = line.partition(" ")
        if not rewrite:
            continue
        # key is `url.<base>.insteadof`; strip the fixed prefix/suffix.
        base = key[len("url."):-len(".insteadof")]
        if url.startswith(rewrite) and len(rewrite) > len(best_rewrite):
            best_rewrite = rewrite
            best_base = base
    if best_rewrite:
        return best_base + url[len(best_rewrite):]
    return url


def clone_url_from_entry(e: LockEntry) -> str:
    """Resolve a LockEntry to a `git clone`-able URL.

    v1 lock entries carry only `source` (e.g. `owner/repo`) + `sourceType`,
    so the read path has to synthesise the URL the same way the v3 writer
    does — otherwise `ensure_project_canonical` hands git a bare owner/repo
    string and the clone fails (#159).

    For synthesised github/gitlab HTTPS URLs we additionally honour the user's
    `insteadOf` rewrites so SSH-only hosts clone over SSH (#251). An explicit
    `sourceUrl` or a local path is returned verbatim — git still rewrites it
    natively at clone time, but we don't second-guess an explicit URL.
    """
    url_from_extras = e.extras.get("sourceUrl")
    if isinstance(url_from_extras, str) and url_from_extras:
        return url_from_extras
    if e.source_type == "github" and "/" in e.source:
        return _apply_insteadof(f"https://github.com/{e.source}.git")
    if e.source_type == "gitlab" and "/" in e.source:
        return _apply_insteadof(f"https://gitlab.com/{e.source}.git")
    return e.source


def _entry_to_dict_v3(e: LockEntry) -> dict:
    now = _now_iso()
    out: dict[str, object] = {
        "source": e.source,
        "sourceType": e.source_type,
        "sourceUrl": clone_url_from_entry(e),
    }
    if e.ref is not None:
        out["ref"] = e.ref
    if e.skill_path is not None:
        out["skillPath"] = e.skill_path
    if e.agent_path is not None:
        out["agentPath"] = e.agent_path
    if e.pi_extension_path is not None:
        out["piExtensionPath"] = e.pi_extension_path
    if e.parent_url is not None:
        out["parentUrl"] = e.parent_url
    if e.read_only:
        out["readOnly"] = True
    if e.upstream_sha is not None:
        out["skillFolderHash"] = e.upstream_sha
    out["installedAt"] = e.extras.get("installedAt") or now
    out["updatedAt"] = now
    # Carry through any other v3 fields we observed (e.g. pluginName) and
    # anything else genuinely unknown.
    for k, v in e.extras.items():
        if k in {"sourceUrl", "installedAt", "updatedAt", "skillFolderHash"}:
            continue
        out[k] = v
    return out


def read_lock(path: Path) -> LockFile:
    try:
        raw = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return LockFile(version=CURRENT_VERSION, skills={})
    if not isinstance(raw, dict):
        return LockFile(version=CURRENT_VERSION, skills={})
    version = raw.get("version")
    if version not in SUPPORTED_VERSIONS:
        return LockFile(version=CURRENT_VERSION, skills={})
    skills_raw = raw.get("skills") or {}
    if not isinstance(skills_raw, dict):
        return LockFile(version=CURRENT_VERSION, skills={})
    from_dict = _entry_from_dict_v1 if version == 1 else _entry_from_dict_v3
    skills = {
        name: from_dict(d)
        for name, d in skills_raw.items()
        if isinstance(d, dict)
    }
    wrapper_extras: dict[str, object] = {}
    if version == 3:
        for k in _V3_WRAPPER_FIELDS:
            if k in raw:
                wrapper_extras[k] = raw[k]
    return LockFile(version=version, skills=skills, wrapper_extras=wrapper_extras)


def write_lock(path: Path, lock: LockFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if lock.version == 3:
        to_dict = _entry_to_dict_v3
    else:
        to_dict = _entry_to_dict_v1
    sorted_skills = {k: to_dict(lock.skills[k]) for k in sorted(lock.skills)}
    body: dict[str, object] = {"version": lock.version, "skills": sorted_skills}
    if lock.version == 3:
        for k, v in lock.wrapper_extras.items():
            body[k] = v
    # Atomic write: a crash mid-write must not truncate the lock and lose every
    # skill (read_lock returns an empty lock on JSONDecodeError). Write to a
    # sibling temp file, then os.replace into place — replace is atomic on the
    # same filesystem.
    text = json.dumps(body, indent=2) + "\n"
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def add_entry(lock: LockFile, slug: str, entry: LockEntry) -> LockFile:
    new_skills = dict(lock.skills)
    new_skills[slug] = entry
    return LockFile(
        version=lock.version, skills=new_skills,
        wrapper_extras=dict(lock.wrapper_extras),
    )


def remove_entry(lock: LockFile, slug: str) -> LockFile:
    if slug not in lock.skills:
        return lock
    new_skills = {k: v for k, v in lock.skills.items() if k != slug}
    return LockFile(
        version=lock.version, skills=new_skills,
        wrapper_extras=dict(lock.wrapper_extras),
    )
