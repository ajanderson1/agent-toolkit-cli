"""`pi-extension add <source>` core: global-only.

Source classification (spec §3):
  npm:<spec>            -> registry-tracked: record a lock entry, NO clone.
  git:/https/ssh/local  -> store-owned: clone into the global library, record
                           a lock entry with pi_extension_path=<slug>.

Mirrors skill_add's global-only posture. Lock is written ONLY after a
successful clone (store-owned) — never before (#283)."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.pi_extension_paths import library_lock_path, library_pi_extension_path
from agent_toolkit_cli.skill_source import ParsedSource, SourceParseError, parse_source


class AddError(RuntimeError):
    """pi-extension add failed."""


def _npm_slug(spec: str) -> str:
    # "npm:@scope/name" -> "@scope/name"
    return spec.split(":", 1)[1]


def looks_like_sha(ref: str | None) -> bool:
    """True when `ref` can only sensibly be a commit SHA (lowercase hex,
    7-40 chars — git's abbreviated-to-full range).

    Why a heuristic is safe both ways: `git clone --branch` rejects a 40-hex
    *branch name* anyway, so classifying one as a SHA is strictly more
    correct than today; and a short all-hex *tag* (e.g. `abc1234`) classified
    as a SHA still resolves — `fetch_ref` + `checkout` accept tag names too.
    """
    return bool(ref) and re.fullmatch(r"[0-9a-f]{7,40}", ref) is not None


def _derive_slug(parsed: ParsedSource) -> str | None:
    """Derive a default slug from a parsed source (mirrors skill add's _add_single)."""
    if parsed.owner_repo:
        repo = parsed.owner_repo.split("/", 1)[1]
        # Strip common '-extension' / '-ext' suffixes, or just use repo name.
        return repo
    # local absolute path: use the final path component
    return Path(parsed.url).name or None


def add(
    *,
    source: str,
    slug: str | None,
    env: dict[str, str] | None = None,
) -> str:
    """Add a Pi extension to the global library. Returns the slug.

    npm:<spec>  -> registry-tracked lock entry only (no clone).
    everything else -> store-owned: clone into the library, then write lock.
    Lock is written ONLY after a successful clone (#283 class of bug).
    """
    lock_path = library_lock_path(env={})

    if source.startswith("npm:"):
        ext_slug = slug or _npm_slug(source)
        lock = read_lock(lock_path)
        if ext_slug in lock.skills and lock.skills[ext_slug].source == source:
            return ext_slug  # idempotent
        entry = LockEntry(source=source, source_type="npm")
        write_lock(lock_path, add_entry(lock, ext_slug, entry))
        return ext_slug

    # Store-owned: parse + clone into the library, THEN write the lock.
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise AddError(str(exc)) from exc

    ext_slug_maybe: str | None = slug or _derive_slug(parsed)
    if not ext_slug_maybe:
        raise AddError(
            f"Cannot derive a slug from {source!r}; pass --slug explicitly"
        )
    ext_slug = ext_slug_maybe  # narrowed: not None past this point

    canonical = library_pi_extension_path(ext_slug, env={})
    if canonical.exists():
        if skill_git.is_git_repo(canonical):
            # Valid store copy — verify source matches, else refuse (mirror
            # skill add). Idempotent success ONLY over a valid repo.
            lock = read_lock(lock_path)
            existing = lock.skills.get(ext_slug)
            requested = parsed.owner_repo or parsed.url
            if existing is not None and existing.source != requested:
                raise AddError(
                    f"{ext_slug}: library already has a different source "
                    f"({existing.source!r}); run `pi-extension remove {ext_slug}` first"
                )
            return ext_slug
        # #347: exists but NOT a git repo — a half-written/empty dir left by a
        # partially-failed cleanup. Treat as not-present: remove it and fall
        # through to the clone path below (which rewrites the lock entry).
        shutil.rmtree(canonical, ignore_errors=True)

    canonical.parent.mkdir(parents=True, exist_ok=True)
    # `git clone --branch` accepts only branch/tag names — a raw SHA must be
    # cloned at HEAD then fetched + checked out (the import pattern, #259).
    pin_sha = parsed.ref if looks_like_sha(parsed.ref) else None
    # May raise GitError -> no lock write (lock honesty, #283).
    skill_git.clone(
        parsed.url, canonical, ref=None if pin_sha else parsed.ref, env=env,
    )
    if pin_sha and skill_git.is_git_repo(canonical):
        # fetch_ref is BEST-EFFORT: a full clone already holds every
        # ref-reachable object, so the fetch only rescues full-SHA pins
        # not reachable from advertised tips — and it ALWAYS fails for
        # abbreviated pins (git fetch accepts only remote refs and full
        # object IDs, while checkout resolves abbreviations locally).
        try:
            skill_git.fetch_ref(canonical, ref=pin_sha, env=env)
        except skill_git.GitError:
            pass
        # checkout is the FAIL-LOUD authority. Deliberate divergence from
        # import's swallow-and-stay-at-HEAD: add is a single explicit pin —
        # silently landing on the wrong commit would violate fail-loud.
        # Clean up the clone so a failed pin leaves no orphaned store dir
        # (#313) and no lock entry (#283).
        try:
            skill_git.checkout(canonical, ref=pin_sha, env=env)
        except skill_git.GitError:
            shutil.rmtree(canonical, ignore_errors=True)
            raise

    # Clone succeeded -> safe to record the lock entry.
    if skill_git.is_git_repo(canonical):
        try:
            upstream_sha: str | None = skill_git.remote_head_sha(
                canonical,
                ref=skill_git.resolve_ref(parsed.ref, canonical, env=env),
                env=env,
            )
        except skill_git.GitError:
            upstream_sha = None
        try:
            local_sha: str | None = skill_git.head_sha(canonical, env=env)
        except skill_git.GitError:
            local_sha = None
    else:
        upstream_sha = None
        local_sha = None

    lock = read_lock(lock_path)
    entry = LockEntry(
        source=parsed.owner_repo or parsed.url,
        source_type=parsed.type,
        ref=parsed.ref,
        pi_extension_path=ext_slug,
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, ext_slug, entry))
    return ext_slug
