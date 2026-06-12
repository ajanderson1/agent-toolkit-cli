"""Diagnose pi-extension installation drift.

Pure engine: diagnose() reads the lock + filesystem and returns Findings.
Each Finding carries an idempotent fix_action.apply() closure the CLI calls
after user confirmation. No mutation happens here.

extensions[] OBSERVE-ONLY guarantee:
  This module reads extensions[] from settings.json (via _pi_settings) to
  detect orphaned override entries (paths in extensions[] that don't exist on
  disk), but it NEVER adds, removes, edits, or reorders any extensions[] entry.
  The fix_action for orphaned extensions[] entries is None (report-only).

Fact-check finding (0.77.0 package-manager.js):
  extensions[] is an OVERRIDE-FILTER (not a path-list). Verified in
  package-manager.js at isEnabledByOverrides() (line ~502): the function
  receives the auto-discovered paths from ~/.pi/agent/extensions/ and the
  extensions[] array as override patterns (!, +, - prefix semantics). This
  matches the #109 reading. Therefore: doctor does not create inventory rows
  from extensions[] entries; it only checks whether the paths referenced by
  those entries still exist on disk, and reports missing ones as orphaned
  overrides (informational, report-only).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from agent_toolkit_cli import _pi_settings, skill_git
from agent_toolkit_cli.pi_extension_add import looks_like_sha
from agent_toolkit_cli.pi_extension_lock import LockFile, read_lock
from agent_toolkit_cli.pi_extension_paths import (
    Scope,
    library_pi_extension_path,
    lock_file_path,
    pi_extension_dir,
)


FindingType = Literal[
    "missing_canonical",
    "half_dir",             # canonical exists but is not a git repo (#347)
    "drifted_symlink",
    "stray_symlink",
    "dirty_tree",
    "orphaned_override",    # extensions[] entry whose path is missing on disk
    "squatted_projection",  # projection slot occupied by a foreign non-symlink entry
]


@dataclass(frozen=True)
class FixAction:
    description: str
    shell_preview: str
    apply: Callable[[], None]


@dataclass(frozen=True)
class Finding:
    finding_type: FindingType
    slug: str
    scope: Scope
    path: Path
    detail: str
    fix_action: FixAction | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def diagnose(
    *,
    slugs: tuple[str, ...] | None,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> list[Finding]:
    """Return all findings for the requested scope.

    slugs=None scans every slug in the lock AND every symlink in the
    extensions/ dir for strays. Otherwise scans only the named slugs.
    """
    # Determine the home for global-scope settings lookup.
    effective_home = home or Path.home()

    lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
    targets = (
        tuple(sorted(lock.skills))
        if slugs is None
        else tuple(s for s in slugs if s in lock.skills)
    )
    findings: list[Finding] = []

    for slug in targets:
        findings.extend(_check_slug(
            slug=slug, scope=scope, home=home, project=project,
            entry=lock.skills[slug], lock=lock,
        ))

    if slugs is None:
        findings.extend(_scan_stray_symlinks(
            scope=scope, home=home, project=project, lock=lock,
        ))
        # extensions[] orphan check (observe-only — no fix_action that mutates).
        findings.extend(_scan_orphaned_overrides(
            scope=scope, home=effective_home, project=project,
        ))

    return findings


# ---------------------------------------------------------------------------
# Per-slug checks
# ---------------------------------------------------------------------------


def _check_slug(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
    entry: object, lock: LockFile,
) -> list[Finding]:
    findings: list[Finding] = []
    # All store-owned rows have a store copy in the global library.
    if getattr(entry, "source_type", None) != "npm":
        canonical = library_pi_extension_path(slug)
        if not canonical.exists():
            findings.append(Finding(
                finding_type="missing_canonical", slug=slug, scope=scope,
                path=canonical,
                detail=(
                    f"lock has '{slug}' but store copy is gone. "
                    f"Source: {getattr(entry, 'source', '?')}"
                ),
                fix_action=_make_reclone_action(slug=slug, entry=entry),
            ))
            # Can't check projection if canonical is gone.
            return findings

        if not skill_git.is_git_repo(canonical):
            # #347: exists but not a git repo — a half-written/failed clone.
            findings.append(Finding(
                finding_type="half_dir", slug=slug, scope=scope,
                path=canonical,
                detail=(
                    f"store copy at {canonical} exists but is not a git repo "
                    f"(partial/failed clone). Source: {getattr(entry, 'source', '?')}"
                ),
                fix_action=_make_reclone_action(slug=slug, entry=entry, force=True),
            ))
            # Can't check projection/dirty-tree over a broken store.
            return findings

        # Check dirty working tree (informational).
        if skill_git.is_git_repo(canonical):
            if skill_git.status(canonical, env=None) == skill_git.GitWorkingTreeStatus.DIRTY:
                findings.append(Finding(
                    finding_type="dirty_tree", slug=slug, scope=scope,
                    path=canonical,
                    detail=f"working tree at {canonical} has uncommitted changes",
                    fix_action=None,
                ))

    # Check the projection symlink.
    try:
        link = pi_extension_dir(slug, scope=scope, home=home, project=project)
    except ValueError:
        return findings  # scope params incomplete

    # Hoist canonical_path so both the is_symlink and elif arms can reference it.
    canonical_path = library_pi_extension_path(slug)

    if link.is_symlink():
        target = link.resolve()
        if target != canonical_path.resolve():
            findings.append(Finding(
                finding_type="drifted_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"symlink at {link} points to {target}, "
                    f"expected {canonical_path}"
                ),
                fix_action=_make_relink_action(link=link, canonical=canonical_path),
            ))
    elif link.exists():
        # A real non-symlink file/dir is squatting the projection slot that
        # should hold our symlink.  pi-extension install already refuses to
        # overwrite it; doctor surfaces the problem so the user can act.
        # fix_action is intentionally None — we never auto-delete user data.
        findings.append(Finding(
            finding_type="squatted_projection", slug=slug, scope=scope,
            path=link,
            detail=(
                f"{link} is occupied by a real "
                f"{'directory' if link.is_dir() else 'file'} "
                f"(not a symlink owned by the toolkit). "
                f"Expected: our symlink → {canonical_path}. "
                f"The slot is squatted — pi-extension install already refuses "
                f"to overwrite it. Remove or relocate the foreign entry manually."
            ),
            fix_action=None,
        ))

    return findings


# ---------------------------------------------------------------------------
# Stray symlink scan
# ---------------------------------------------------------------------------


def _scan_stray_symlinks(
    *, scope: Scope, home: Path | None, project: Path | None, lock: LockFile,
) -> list[Finding]:
    """Find symlinks in Pi's extensions/ dir whose slug is not in the lock."""
    findings: list[Finding] = []
    known = set(lock.skills)
    try:
        # pi_extension_dir gives <root>/<slug>; parent is the extensions/ root.
        sample_link = pi_extension_dir("_dummy_", scope=scope, home=home, project=project)
        ext_root = sample_link.parent
    except ValueError:
        return findings

    if not ext_root.is_dir():
        return findings

    try:
        entries = list(ext_root.iterdir())
    except OSError:
        return findings

    for path in entries:
        if not path.is_symlink():
            continue
        slug = path.name
        if slug in known:
            continue
        try:
            target = path.readlink()
        except OSError:
            target = Path("(unreadable)")
        findings.append(Finding(
            finding_type="stray_symlink", slug=slug, scope=scope,
            path=path,
            detail=(
                f"{path} -> {target}: '{slug}' is not in the {scope} lock; "
                f"leftover from an older install"
            ),
            fix_action=_make_unlink_action(link=path),
        ))
    return findings


# ---------------------------------------------------------------------------
# extensions[] orphan scan (observe-only: never mutates extensions[])
# ---------------------------------------------------------------------------


def _strip_prefix(entry: str) -> str:
    """Strip override prefixes (!, +, -) to get the raw path."""
    if entry and entry[0] in ("!", "+", "-"):
        return entry[1:]
    return entry


def _scan_orphaned_overrides(
    *, scope: Scope, home: Path, project: Path | None,
) -> list[Finding]:
    """Report extensions[] entries whose resolved path is missing on disk.

    extensions[] is an override-filter (verified against 0.77.0 package-
    manager.js): entries enable/disable auto-discovered paths in the
    extensions/ dir. An entry pointing at a path that no longer exists on
    disk is an orphaned override — Pi ignores it, but it's clutter.

    OBSERVE-ONLY: fix_action is None (never auto-remove or rewrite the array).
    """
    findings: list[Finding] = []
    try:
        ext_entries = _pi_settings.read_extension_paths(
            scope=scope, home=home if scope == "global" else None,
            project=project,
        )
    except _pi_settings.PiSettingsError:
        return findings  # malformed settings: don't crash, just skip

    # Compute the scope base dir (per 0.77.0: global=~/.pi/agent, project=<cwd>/.pi)
    if scope == "global":
        base_dir = home / ".pi" / "agent"
    else:
        if project is None:
            return findings
        base_dir = project / ".pi"

    for raw_entry in ext_entries:
        path_str = _strip_prefix(raw_entry)
        if not path_str:
            continue
        # Resolve relative paths against the scope base dir.
        path = Path(path_str)
        if not path.is_absolute():
            path = base_dir / path
        if not path.exists():
            findings.append(Finding(
                finding_type="orphaned_override", slug=raw_entry, scope=scope,
                path=path,
                detail=(
                    f"extensions[] entry {raw_entry!r} resolves to {path} "
                    f"which does not exist on disk (orphaned override). "
                    f"Note: doctor never auto-removes extensions[] entries — "
                    f"edit settings.json manually if you want to clean this up."
                ),
                fix_action=None,  # NEVER auto-mutate extensions[]
            ))
    return findings


# ---------------------------------------------------------------------------
# Fix-action factories
# ---------------------------------------------------------------------------


def _make_unlink_action(*, link: Path) -> FixAction:
    def _apply() -> None:
        if not link.is_symlink():
            return  # idempotent
        link.unlink()

    return FixAction(
        description=f"Unlink {link}",
        shell_preview=f"rm {link}",
        apply=_apply,
    )


def _make_relink_action(*, link: Path, canonical: Path) -> FixAction:
    def _apply() -> None:
        if link.is_symlink() and link.resolve() == canonical.resolve():
            return  # idempotent
        if link.is_symlink() or link.exists():
            link.unlink()
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(canonical, target_is_directory=True)

    return FixAction(
        description=f"Re-link {link} → {canonical}",
        shell_preview=f"rm {link} && ln -s {canonical} {link}",
        apply=_apply,
    )


def _make_reclone_action(*, slug: str, entry: object, force: bool = False) -> FixAction:
    """Re-clone the store copy from the lock entry's source.

    Pin ONLY when the entry's `ref` is a SHA — NEVER from `upstream_sha`,
    which add() records for every store-owned entry as the observed tip at
    add time; pinning on it would detach every branch-tracking entry at a
    stale SHA (#330 review). `git clone --branch` rejects raw SHAs, so a pin
    is applied post-clone: best-effort fetch_ref (rescues full-SHA wants;
    always fails for abbreviations), then checkout as the fail-loud
    authority. A failed checkout removes the partial clone and re-raises —
    fail loud, no orphan dir (#313).
    """
    source = getattr(entry, "source", "")
    ref = getattr(entry, "ref", None)
    canonical = library_pi_extension_path(slug)

    ref_is_sha = looks_like_sha(ref)
    pin_sha = ref if ref_is_sha else None
    clone_ref = None if ref_is_sha else ref

    def _apply() -> None:
        if canonical.exists():
            if not force:
                return  # idempotent (missing_canonical: a race re-created it)
            # half_dir (#347): a non-repo dir is squatting the path — remove
            # it so the clone below has a clean target.
            shutil.rmtree(canonical, ignore_errors=True)
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(source, canonical, ref=clone_ref, env=None)
        if pin_sha and skill_git.is_git_repo(canonical):
            try:
                skill_git.fetch_ref(canonical, ref=pin_sha, env=None)
            except skill_git.GitError:
                pass  # best-effort; checkout resolves locally
            try:
                skill_git.checkout(canonical, ref=pin_sha, env=None)
            except skill_git.GitError:
                shutil.rmtree(canonical, ignore_errors=True)
                raise

    return FixAction(
        description=f"Re-clone {slug} from {source}",
        shell_preview=(
            f"git clone{(' --branch ' + clone_ref) if clone_ref else ''} "
            f"{source} {canonical}"
            + (f" && git -C {canonical} checkout {pin_sha}" if pin_sha else "")
        ),
        apply=_apply,
    )


