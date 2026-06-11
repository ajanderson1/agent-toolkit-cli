"""Diagnose + repair skill-installation drift.

Pure-ish engine: diagnose() reads lock + filesystem and returns Findings.
Each Finding carries an idempotent fix_action.apply() closure that the
CLI calls after the user confirms. No mutation happens here; that's the
caller's responsibility (via fix_action.apply).
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from agent_toolkit_cli import skill_git
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_cli.skill_install import _should_skip_symlink, _standard_bundle_link
from agent_toolkit_cli.skill_lock import (
    LockEntry, LockFile, add_entry, clone_url_from_entry, read_lock, remove_entry,
    write_lock,
)
from agent_toolkit_cli.skill_paths import (
    Scope, agent_projection_dir, canonical_skill_dir, library_lock_path,
    library_root as _library_root_fn, lock_file_path,
)

FindingType = Literal[
    "missing_canonical", "drifted_symlink",
    "wrong_type_bundle", "orphan_symlink", "foreign_symlink",
    "dirty_tree", "lock_source_mismatch", "stray_symlink",
    "orphan_canonical", "stray_bundle_dir", "unlisted",
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
        findings.extend(_scan_orphan_canonicals(
            scope=scope, home=home, project=project, lock=lock,
        ))
        findings.extend(_scan_stray_bundle_dirs(
            scope=scope, home=home, project=project, lock=lock,
        ))
        findings.extend(_scan_unlisted_entries(
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
        if cfg.is_standard:
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
                finding_type="stray_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"{link} -> {target}: '{slug}' is not in the {scope} "
                    f"lock; symlink is a leftover from an older install"
                ),
                fix_action=_make_unlink_action(link=link),
            ))
    return findings


def _scan_orphan_canonicals(
    *, scope: Scope, home: Path | None, project: Path | None, lock: LockFile,
) -> list[Finding]:
    """Find entries in the per-project external store with no lock entry.

    Project scope only. After a non-destructive uninstall the external canonical
    is left behind; over time the store accumulates unreferenced clones. Also
    sweeps `*.bak-*` dirs left by migration collisions. The fix removes them.
    """
    if scope != "project":
        return []
    assert project is not None
    from agent_toolkit_cli.skill_paths import project_store_root

    store = project_store_root(project)
    if not store.is_dir():
        return []
    known = set(lock.skills)
    findings: list[Finding] = []
    try:
        entries = sorted(store.iterdir())
    except OSError:
        return []
    for path in entries:
        name = path.name
        if name == "_parents":
            continue  # parent cache is managed by install, not an orphan
        is_bak = ".bak-" in name
        if name in known and not is_bak:
            continue  # referenced canonical — keep
        slug = name.split(".bak-")[0] if is_bak else name
        detail = (
            f"{path}: migration backup, safe to remove"
            if is_bak
            else f"{path}: '{name}' has no entry in the project lock "
                 f"(orphaned canonical from a prior uninstall)"
        )
        findings.append(Finding(
            finding_type="orphan_canonical", slug=slug, scope=scope,
            path=path, detail=detail,
            fix_action=_make_rmtree_action(path=path),
        ))
    return findings


def _scan_stray_bundle_dirs(
    *, scope: Scope, home: Path | None, project: Path | None, lock: LockFile,
) -> list[Finding]:
    """Find orphan REAL directories in the standard-bundle root ~/.agents/skills.

    Global scope only. A correctly installed global standard skill is a *symlink*
    at ~/.agents/skills/<slug> → the library canonical; a real dir there whose slug
    is in the lock is a `wrong_type_bundle` case (handled by _check_slug). What this
    scan catches is the remainder: real dirs whose slug is NOT in the lock (orphan
    strays), and doctor's own `*.bak-doctor-*` leftovers that nothing else reaps.

    Strays are moved to a `.bak-doctor-*` backup (non-destructive — they may hold
    un-locked skill files). `.bak-*` leftovers are removed outright (already backups).
    """
    if scope != "global":
        return []
    root = _standard_bundle_root()
    if not root.is_dir():
        return []
    known = set(lock.skills)
    findings: list[Finding] = []
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return []
    for path in entries:
        if path.is_symlink() or not path.is_dir():
            continue  # symlinks are correct install artifacts; ignore files
        name = path.name
        is_bak = ".bak-" in name
        if name in known and not is_bak:
            continue  # real dir IS in lock → wrong_type_bundle's job, not stray
        if is_bak:
            slug = name.split(".bak-")[0]
            findings.append(Finding(
                finding_type="stray_bundle_dir", slug=slug, scope=scope,
                path=path,
                detail=f"{path}: leftover doctor backup, safe to remove",
                fix_action=_make_rmtree_action(path=path),
            ))
        else:
            findings.append(Finding(
                finding_type="stray_bundle_dir", slug=name, scope=scope,
                path=path,
                detail=(
                    f"{path}: '{name}' is a real directory in the standard "
                    f"bundle but has no entry in the global lock"
                ),
                fix_action=_make_backup_dir_action(path=path),
            ))
    return findings


def _make_backup_dir_action(*, path: Path) -> FixAction:
    """Move a directory to a `.bak-doctor-<stamp>` sibling (non-destructive).

    Mirrors the backup half of `_make_bundle_repair_action` without the relink:
    a stray has no canonical to point at. Stamped at apply()-time so repeat runs
    don't collide.
    """
    def _apply() -> None:
        if not path.is_dir() or path.is_symlink():
            return  # idempotent: already moved / not a real dir
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path.rename(path.with_name(f"{path.name}.bak-doctor-{stamp}"))

    return FixAction(
        description=f"Back up stray directory {path} to a .bak-doctor-* sibling",
        shell_preview=f"mv {path} {path}.bak-doctor-$(date +%Y%m%d-%H%M%S)",
        apply=_apply,
    )


def _make_rmtree_action(*, path: Path) -> FixAction:
    """A FixAction that removes a directory tree (or symlink) at `path`."""
    def _apply() -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    return FixAction(
        description=f"Remove {path}",
        shell_preview=f"rm -rf {path}",
        apply=_apply,
    )


def _make_reclone_action(
    *, slug: str, scope: Scope, home: Path | None, project: Path | None,
    entry: LockEntry,
) -> FixAction:
    """Repair a missing canonical.

    Single-skill repo: clone the repo root flat into the canonical dir.

    Monorepo skill (entry.parent_url set): clone the PARENT repo into the
    shared `_parents/<owner>/<repo>` cache and re-symlink the canonical to
    `parent/<skill_path>`, mirroring skill_install.ensure_project_canonical.
    A flat `git clone <parent_url> <canonical>` would dump the whole parent
    repo into the slug dir (SKILL.md would sit at <canonical>/<skill_path>/
    instead of <canonical>/), so the monorepo branch is required for correct
    repair — especially for nested skill_paths like 'aj-workflows/aj-flow'.
    """
    canonical = canonical_skill_dir(slug, scope=scope, home=home, project=project)
    # Repair clones a fresh repo, so there's no local clone to detect the
    # default branch from. Pass the pinned ref when one exists; otherwise pass
    # None so `git clone` follows the remote's own default branch — forcing
    # `--branch main` would fail outright for a `master`-based upstream.
    ref = entry.ref

    if entry.parent_url is not None:
        return _make_monorepo_reclone_action(
            slug=slug, scope=scope, project=project, entry=entry, ref=ref,
            canonical=canonical,
        )

    url = clone_url_from_entry(entry)

    def _apply() -> None:
        if canonical.exists():
            return  # idempotent
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(url, canonical, ref=ref, env=None)

    preview_ref = f" --branch {ref}" if ref else ""
    return FixAction(
        description=f"Re-clone {slug} from {url}",
        shell_preview=f"git clone{preview_ref} {url} {canonical}",
        apply=_apply,
    )


def _make_monorepo_reclone_action(
    *, slug: str, scope: Scope, project: Path | None, entry: LockEntry,
    ref: str | None, canonical: Path,
) -> FixAction:
    """Repair a missing monorepo canonical: clone parent → symlink subpath.

    Clones (or reuses) the parent repo in the shared `_parents/` cache and
    points the canonical symlink at `parent/<skill_path>`. Idempotent and
    depth-agnostic: `skill_path` may be a multi-segment path.
    """
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, project_parents_root,
    )

    if entry.skill_path is None:
        raise InstallError(f"{slug}: monorepo lock entry missing skillPath")
    parts = entry.source.split("/", 1)
    if len(parts) != 2:
        raise InstallError(
            f"{slug}: monorepo lock entry has non-owner/repo source "
            f"{entry.source!r}"
        )
    owner, repo = parts
    parents_root = None if scope == "global" else project_parents_root(project)
    parent_dir = parent_clone_path(owner, repo, ref=entry.ref, root=parents_root)
    skill_path = entry.skill_path

    def _apply() -> None:
        if canonical.exists():
            return  # idempotent (symlink already resolves)
        if not parent_dir.exists():
            parent_dir.parent.mkdir(parents=True, exist_ok=True)
            skill_git.clone(entry.parent_url, parent_dir, ref=entry.ref, env=None)
        skill_root = parent_dir / skill_path
        if not (skill_root / "SKILL.md").exists():
            raise InstallError(
                f"{slug}: {skill_path}/SKILL.md not found in parent clone "
                f"at {parent_dir}"
            )
        if canonical.is_symlink():
            canonical.unlink()  # broken symlink: parent clone was gone
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.symlink_to(skill_root)

    return FixAction(
        description=(
            f"Re-clone parent {entry.source} and re-link {slug} "
            f"→ {skill_path}"
        ),
        shell_preview=(
            f"git clone{f' --branch {ref}' if ref else ''} "
            f"{entry.parent_url} {parent_dir} && "
            f"ln -s {parent_dir / skill_path} {canonical}"
        ),
        apply=_apply,
    )


def _scan_unlisted_entries(
    *, scope: Scope, home: Path | None, project: Path | None, lock: LockFile,
) -> list[Finding]:
    """#360 AC4: project lock entries whose slug is missing from the library lock.

    The install is functional (project canonicals are independent of the
    library); the finding flags that the library no longer tracks the slug
    and offers to re-add it from the entry's recorded source+ref."""
    if scope != "project":
        return []
    lib_lock = read_lock(library_lock_path())
    findings: list[Finding] = []
    for slug, entry in sorted(lock.skills.items()):
        if slug in lib_lock.skills:
            continue
        findings.append(Finding(
            finding_type="unlisted", slug=slug, scope=scope,
            path=lock_file_path(scope=scope, home=home, project=project),
            detail=(
                "project lock entry's slug is missing from the library lock "
                "(install is functional; the library no longer tracks it)"
            ),
            fix_action=_make_readd_library_action(slug=slug, entry=entry),
        ))
    return findings


def _make_readd_library_action(*, slug: str, entry: LockEntry) -> FixAction:
    """Re-add an unlisted slug to the library from its recorded source+ref.

    Materialises the library canonical (reusing the reclone machinery at
    global scope — monorepo entries take the parent-clone branch) and writes
    the library lock entry. SHAs are reset to None; `skill update` re-resolves
    them."""
    reclone = _make_reclone_action(
        slug=slug, scope="global", home=None, project=None, entry=entry,
    )

    def _apply() -> None:
        reclone.apply()
        lib_path = library_lock_path()
        lib_lock = read_lock(lib_path)
        if slug not in lib_lock.skills:
            write_lock(lib_path, add_entry(
                lib_lock, slug,
                dataclasses.replace(entry, upstream_sha=None, local_sha=None),
            ))

    ref_arg = f" --ref {entry.ref}" if entry.ref else ""
    return FixAction(
        description=f"Re-add {slug} to the library from {entry.source}",
        shell_preview=f"agent-toolkit-cli skill add {entry.source}{ref_arg} --slug {slug}",
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
    """Return (agent_name, projection_path) tuples for every non-standard
    real agent at the given scope. Standard bundle handled separately.
    """
    out: list[tuple[str, Path]] = []
    for name, cfg in AGENTS.items():
        if cfg.is_standard:
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


def _standard_bundle_root() -> Path:
    """Root of the v2.1 standard-bundle layout: ~/.agents/skills.

    Mirrors `skill_install._standard_bundle_link` (which is `<root>/<slug>`).
    """
    return Path.home() / ".agents" / "skills"


def _is_standard_bundle_target(target: Path) -> bool:
    """True when `target` lives inside the standard-bundle root.

    On a v2.1 → v2.2 migration the per-harness symlinks point at
    `~/.agents/skills/<slug>` (a real dir or a transitional symlink). The
    classification should be `drifted_symlink` (re-link to library) rather
    than `foreign_symlink` (report-only).
    """
    return _is_inside(target, _standard_bundle_root())


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
            finding_type="missing_canonical", slug=slug, scope=scope,
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
                finding_type="orphan_symlink", slug=slug, scope=scope,
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
            if _is_standard_bundle_target(target):
                findings.append(Finding(
                    finding_type="drifted_symlink", slug=slug, scope=scope,
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
                finding_type="foreign_symlink", slug=slug, scope=scope,
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
            finding_type="drifted_symlink", slug=slug, scope=scope,
            path=link,
            detail=(
                f"{agent_name} symlink at {link} points to {target}, "
                f"expected {canonical}"
            ),
            fix_action=_make_relink_action(link=link, canonical=canonical),
        ))
    if scope == "global":
        bundle = _standard_bundle_link(slug)
        if bundle.exists() and not bundle.is_symlink():
            findings.append(Finding(
                finding_type="wrong_type_bundle", slug=slug, scope=scope,
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
                finding_type="dirty_tree", slug=slug, scope=scope,
                path=canonical,
                detail=f"working tree at {canonical} has uncommitted changes",
                fix_action=None,
            ))
    if skill_git.is_git_repo(canonical):
        observed = _remote_origin_url(canonical)
        expected = clone_url_from_entry(entry)
        if observed is not None and _normalise_git_url(observed) != _normalise_git_url(expected):
            findings.append(Finding(
                finding_type="lock_source_mismatch", slug=slug, scope=scope,
                path=canonical,
                detail=(
                    f"lock source {expected!r} != git remote origin "
                    f"{observed!r}"
                ),
                fix_action=None,
            ))
    return findings
