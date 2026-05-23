"""Diagnose + repair skill-installation drift.

Pure-ish engine: diagnose() reads lock + filesystem and returns Findings.
Each Finding carries an idempotent fix_action.apply() closure that the
CLI calls after the user confirms. No mutation happens here; that's the
caller's responsibility (via fix_action.apply).
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_cli.skill_install import _should_skip_symlink, _universal_bundle_link
from agent_toolkit_cli.skill_lock import (
    LockEntry, LockFile, clone_url_from_entry, read_lock, remove_entry, write_lock,
)
from agent_toolkit_cli.skill_paths import (
    Scope, agent_projection_dir, canonical_skill_dir, library_root as _library_root_fn,
    lock_file_path,
)

FindingKind = Literal[
    "missing_canonical", "drifted_symlink",
    "wrong_type_bundle", "orphan_symlink", "foreign_symlink",
    "dirty_tree", "lock_source_mismatch", "stray_symlink",
]


@dataclass(frozen=True)
class FixAction:
    description: str
    shell_preview: str
    apply: Callable[[], None]


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    slug: str
    scope: Scope
    path: Path
    detail: str
    fix_action: FixAction | None


def diagnose(
    *,
    slugs: tuple[str, ...] | None,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    repair_foreign: bool = False,
) -> list[Finding]:
    """Return all findings for the requested scope.

    slugs=None scans every slug in the lock AND every projection dir for
    stray symlinks (links whose basename isn't in the scope's lock).
    Otherwise scans only the named slugs and skips the stray scan.
    """
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
            repair_foreign=repair_foreign,
        ))
    if slugs is None:
        findings.extend(_scan_stray_symlinks(
            scope=scope, home=home, project=project, lock=lock,
        ))
    return findings


def _runtime_global_skills_dir(cfg, runtime_home: Path) -> Path:
    """Return cfg.global_skills_dir with its import-time HOME prefix swapped
    for runtime_home.

    skill_agents resolves HOME once at import. Tests that monkeypatch
    Path.home() afterwards leave the AGENTS dict pointing at the real
    user's home dirs. Re-deriving the path against runtime_home keeps the
    stray scan honest under test sandboxes without invalidating production
    behaviour (where Path.home() == import-time HOME).
    """
    from agent_toolkit_cli.skill_agents import HOME as _IMPORT_HOME
    p = cfg.global_skills_dir
    if runtime_home == _IMPORT_HOME:
        return p
    try:
        relative = p.relative_to(_IMPORT_HOME)
    except ValueError:
        return p
    return runtime_home / relative


def _scan_stray_symlinks(
    *, scope: Scope, home: Path | None, project: Path | None, lock: LockFile,
) -> list[Finding]:
    """Find symlinks in projection dirs whose basename isn't in the lock.

    These are leftover links from an older layout, a manually-removed install,
    or a renamed slug. The fix is to remove the symlink — there's no canonical
    to point it at.
    """
    findings: list[Finding] = []
    known = set(lock.skills)
    seen: set[Path] = set()
    runtime_home = Path.home()
    for agent_name, cfg in AGENTS.items():
        if cfg.is_universal:
            continue
        skip, _ = _should_skip_symlink(
            agent_name=agent_name, scope=scope, project=project,
        )
        if skip:
            continue
        if scope == "global":
            parent = _runtime_global_skills_dir(cfg, runtime_home)
        else:
            assert project is not None
            parent = project / cfg.skills_dir
        if parent in seen:
            continue
        seen.add(parent)
        if not parent.is_dir():
            continue
        try:
            entries = list(parent.iterdir())
        except OSError:
            continue
        for link in entries:
            if not link.is_symlink():
                continue
            slug = link.name
            if slug in known:
                continue
            try:
                target = link.readlink()
            except OSError:
                target = Path("(unreadable)")
            findings.append(Finding(
                kind="stray_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"{link} -> {target}: '{slug}' is not in the {scope} "
                    f"lock; symlink is a leftover from an older install"
                ),
                fix_action=_make_unlink_action(link=link),
            ))
    return findings


def _make_reclone_action(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
    entry: LockEntry,
) -> FixAction:
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    url = clone_url_from_entry(entry)
    ref = entry.ref or "main"

    def _apply() -> None:
        if canonical.exists():
            return  # idempotent
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(url, canonical, ref=ref, env=None)

    return FixAction(
        description=f"Re-clone {slug} from {url}",
        shell_preview=f"git clone --branch {ref} {url} {canonical}",
        apply=_apply,
    )


def make_remove_entry_action(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
) -> FixAction:
    """Return a FixAction that drops `slug` from the lock for the given scope.

    Idempotent: removing a missing entry is a no-op.
    """
    lock_path = lock_file_path(scope=scope, home=home, project=project)

    def _apply() -> None:
        lock = read_lock(lock_path)
        if slug not in lock.skills:
            return  # idempotent
        write_lock(lock_path, remove_entry(lock, slug))

    return FixAction(
        description=f"Remove {slug} from lock at {lock_path}",
        shell_preview=(
            f"# Edit {lock_path} and delete the \"{slug}\" entry under \"skills\""
        ),
        apply=_apply,
    )


def _projection_paths(
    slug: str, *, scope: Scope, home: Path | None, project: Path | None,
) -> list[tuple[str, Path]]:
    """Return (agent_name, projection_path) tuples for every non-universal
    real agent at the given scope. Universal bundle handled separately.
    """
    out: list[tuple[str, Path]] = []
    for name, cfg in AGENTS.items():
        if cfg.is_universal:
            # Skip rule fires at both scopes; no per-agent symlink expected.
            continue
        skip, _ = _should_skip_symlink(
            agent_name=name, scope=scope, project=project,
        )
        if skip:
            continue
        out.append((name, agent_projection_dir(
            name, slug, scope=scope, home=home, project=project,
        )))
    return out


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _universal_bundle_root() -> Path:
    """Root of the v2.1 universal-bundle layout: ~/.agents/skills.

    Mirrors `skill_install._universal_bundle_link` (which is `<root>/<slug>`).
    """
    return Path.home() / ".agents" / "skills"


def _is_universal_bundle_target(target: Path) -> bool:
    """True when `target` lives inside the universal-bundle root.

    On a v2.1 → v2.2 migration the per-harness symlinks point at
    `~/.agents/skills/<slug>` (a real dir or a transitional symlink). The
    classification should be `drifted_symlink` (re-link to library) rather
    than `foreign_symlink` (report-only).
    """
    return _is_inside(target, _universal_bundle_root())


def _expected_target_root(
    *, scope: Scope, project: Path | None,
) -> Path:
    if scope == "global":
        return _library_root_fn()
    assert project is not None
    return project / ".agents" / "skills"


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
        link.symlink_to(canonical)

    return FixAction(
        description=f"Re-link {link} → {canonical}",
        shell_preview=f"rm {link} && ln -s {canonical} {link}",
        apply=_apply,
    )


def _make_bundle_repair_action(*, bundle: Path, canonical: Path) -> FixAction:
    def _apply() -> None:
        # Idempotent: if it's already a correct symlink, no-op.
        if bundle.is_symlink() and bundle.resolve() == canonical.resolve():
            return
        if bundle.is_dir() and not bundle.is_symlink():
            stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = bundle.with_name(f"{bundle.name}.bak-doctor-{stamp}")
            bundle.rename(backup)
        if bundle.is_symlink():
            bundle.unlink()
        bundle.parent.mkdir(parents=True, exist_ok=True)
        bundle.symlink_to(canonical)

    return FixAction(
        description=(
            f"Back up real directory at {bundle} and replace with symlink to "
            f"{canonical}"
        ),
        shell_preview=(
            f"mv {bundle} {bundle}.bak-doctor-$(date +%Y%m%d-%H%M%S) && "
            f"ln -s {canonical} {bundle}"
        ),
        apply=_apply,
    )


def _remote_origin_url(canonical: Path) -> str | None:
    """Return `git remote get-url origin` for canonical, or None on failure."""
    try:
        proc = skill_git._run(
            ["git", "-C", str(canonical), "remote", "get-url", "origin"],
            env=None,
        )
    except skill_git.GitError:
        return None
    return proc.stdout.strip() or None


_SSH_GIT_URL_RE = re.compile(r"^git@([^:]+):(.+?)(?:\.git)?/?$")
_HTTPS_GIT_URL_RE = re.compile(r"^https?://([^/]+)/(.+?)(?:\.git)?/?$")
_SSH_URL_RE = re.compile(r"^ssh://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$")


def _normalise_git_url(url: str) -> str:
    """Reduce SSH and HTTPS forms to ``host/path`` for equality comparison.

    `git@github.com:foo/bar.git` and `https://github.com/foo/bar.git` both
    collapse to `github.com/foo/bar`. Trailing slashes and the `ssh://` URL
    form are also folded in. Anything that doesn't match any pattern falls
    back to lowercase + trailing-`.git` strip + trailing-slash strip, so
    local paths and unfamiliar URL forms still round-trip sensibly.
    """
    u = url.strip().lower()
    if (m := _SSH_GIT_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if (m := _HTTPS_GIT_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if (m := _SSH_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u


def _check_slug(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
    entry: LockEntry, lock: LockFile, repair_foreign: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    if not canonical.exists():
        findings.append(Finding(
            kind="missing_canonical", slug=slug, scope=scope,
            path=canonical,
            detail=(
                f"lock has {slug} but canonical directory is gone. "
                f"Source: {entry.source}"
            ),
            fix_action=_make_reclone_action(
                slug=slug, scope=scope, home=home, project=project, entry=entry,
            ),
        ))
        return findings  # other checks all assume canonical exists
    canonical_real = canonical.resolve()
    for agent_name, link in _projection_paths(
        slug, scope=scope, home=home, project=project,
    ):
        if not link.is_symlink():
            continue
        target_path = Path(link.readlink())
        if not target_path.is_absolute():
            target_path = (link.parent / target_path).resolve()
        target_exists = target_path.exists()
        if not target_exists:
            findings.append(Finding(
                kind="orphan_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"{agent_name} symlink at {link} points to {target_path} "
                    f"which does not exist"
                ),
                fix_action=_make_unlink_action(link=link),
            ))
            continue
        target = link.resolve()
        if target == canonical_real:
            continue
        expected_root = _expected_target_root(scope=scope, project=project)
        if not _is_inside(target, expected_root):
            if _is_universal_bundle_target(target):
                findings.append(Finding(
                    kind="drifted_symlink", slug=slug, scope=scope,
                    path=link,
                    detail=(
                        f"{agent_name} symlink at {link} points to {target} "
                        f"(v2.1 bundle layout), expected {canonical}"
                    ),
                    fix_action=_make_relink_action(
                        link=link, canonical=canonical,
                    ),
                ))
                continue
            findings.append(Finding(
                kind="foreign_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"{agent_name} symlink at {link} points to {target}, "
                    f"which is outside {expected_root}"
                ),
                fix_action=(
                    _make_unlink_action(link=link) if repair_foreign else None
                ),
            ))
            continue
        findings.append(Finding(
            kind="drifted_symlink", slug=slug, scope=scope,
            path=link,
            detail=(
                f"{agent_name} symlink at {link} points to {target}, "
                f"expected {canonical}"
            ),
            fix_action=_make_relink_action(link=link, canonical=canonical),
        ))
    if scope == "global":
        bundle = _universal_bundle_link(slug)
        if bundle.exists() and not bundle.is_symlink():
            findings.append(Finding(
                kind="wrong_type_bundle", slug=slug, scope=scope,
                path=bundle,
                detail=(
                    f"{bundle} is a real directory; expected symlink to "
                    f"{canonical}"
                ),
                fix_action=_make_bundle_repair_action(
                    bundle=bundle, canonical=canonical,
                ),
            ))
    if skill_git.is_git_repo(canonical):
        if skill_git.status(canonical, env=None) == skill_git.GitWorkingTreeStatus.DIRTY:
            findings.append(Finding(
                kind="dirty_tree", slug=slug, scope=scope,
                path=canonical,
                detail=f"working tree at {canonical} has uncommitted changes",
                fix_action=None,
            ))
    if skill_git.is_git_repo(canonical):
        observed = _remote_origin_url(canonical)
        expected = clone_url_from_entry(entry)
        if observed is not None and _normalise_git_url(observed) != _normalise_git_url(expected):
            findings.append(Finding(
                kind="lock_source_mismatch", slug=slug, scope=scope,
                path=canonical,
                detail=(
                    f"lock source {expected!r} != git remote origin "
                    f"{observed!r}"
                ),
                fix_action=None,
            ))
    return findings
