"""`agent doctor [-g/-p] [--no-fix]` — diagnose agent installation drift.

Detects:
  - missing canonicals (lock entry but no canonical directory)
  - missing content file (canonical exists but <slug>.md absent)
  - dirty working trees (uncommitted changes in the canonical)
  - orphaned projections (projection file exists but no lock entry)
  - orphan canonicals (canonical directory present but no lock entry)
  - standard-slot drift (#361: slot differs from the scope's canonical)
  - cursor-shadow (#361: stale .cursor/agents copy shadowing the slot)
  - standard-slot orphan / unmanaged / dangling-sidecar (#361 sweep)
  - unlisted project entries (#360: project lock entry missing from the
    library lock; inert until #362)

Repair actions are offered interactively unless --no-fix is given.
"""
from __future__ import annotations

import dataclasses
import filecmp
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import click

from agent_toolkit_cli.agent_adapters import _sentinel_path, get_adapter
from agent_toolkit_cli.agent_lock import (
    LockEntry, add_entry, clone_url_from_entry, read_lock, write_lock,
)
from agent_toolkit_cli.agent_paths import (
    Scope,
    canonical_agent_dir,
    library_agent_path,
    library_lock_path,
    lock_file_path,
)
from agent_toolkit_cli.commands.agent._common import scope_and_roots
from agent_toolkit_cli import skill_git


@dataclass
class FixAction:
    shell_preview: str
    apply: Callable[[], None]


def _rm_file_and_sidecar(dest: Path) -> None:
    """Remove a tool-owned file together with its `.attk` ownership sidecar."""
    dest.unlink()
    _sentinel_path(dest).unlink(missing_ok=True)


def _reseed_slot(canonical_content: Path, slot: Path) -> None:
    """Re-seed the standard slot from the canonical and (re)write the `.attk`
    ownership sidecar — consistent with the adapter's adopt-if-identical
    contract: a slot the tool just made byte-equal to the canonical is
    tool-owned."""
    shutil.copy2(canonical_content, slot)
    _sentinel_path(slot).write_text("")


@dataclass
class Finding:
    slug: str
    finding_type: str
    scope: str
    path: Path
    detail: str
    fix_action: FixAction | None = None


# Informational finding types (#361, PM review F1): report-only notices about
# files this tool does NOT manage. They stay visible in the output but never
# fail the exit code or suppress the clean verdict — one hand-authored agent
# in .claude/agents/ (the dir's primary population) must not make doctor
# exit 1 forever. Pre-#361 report-only types (missing-canonical,
# missing-content-file, dirty-canonical) describe MANAGED assets in a bad
# state and keep their original exit-1 semantics. `unlisted` (#360) is
# deliberately NOT here: it is actionable (re-add fix-action) and keeps
# exit-1 semantics.
_INFORMATIONAL_TYPES: frozenset[str] = frozenset({
    "standard-slot-unmanaged",
    "cursor-shadow",
})


def _make_readd_library_action(*, slug: str, entry: LockEntry) -> FixAction:
    """#360: re-add an unlisted agent to the library from its recorded
    source+ref — clone the canonical if missing, then write the library lock
    entry (SHAs reset; `agent update` re-resolves)."""
    canonical = library_agent_path(slug)
    url = clone_url_from_entry(entry)

    def _apply() -> None:
        if not canonical.exists():
            canonical.parent.mkdir(parents=True, exist_ok=True)
            skill_git.clone(url, canonical, ref=entry.ref, env=None)
        lib_path = library_lock_path()
        lib = read_lock(lib_path)
        if slug not in lib.skills:
            write_lock(lib_path, add_entry(
                lib, slug,
                dataclasses.replace(entry, upstream_sha=None, local_sha=None),
            ))

    ref_arg = f" --ref {entry.ref}" if entry.ref else ""
    return FixAction(
        shell_preview=f"agent-toolkit-cli agent add {entry.source}{ref_arg} --slug {slug}",
        apply=_apply,
    )


def _diagnose(
    *,
    slugs: tuple[str, ...] | None,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> list[Finding]:
    findings: list[Finding] = []
    lock_path = lock_file_path(scope=scope, home=home, project=project)
    # read_lock returns an empty LockFile for a missing file — never raises.
    lock = read_lock(lock_path)

    targets = (
        {k: v for k, v in lock.skills.items() if k in set(slugs)}
        if slugs else dict(lock.skills)
    )

    for slug, entry in sorted(targets.items()):
        canonical = library_agent_path(slug)

        # 1. Missing canonical directory.
        if not canonical.exists():
            findings.append(Finding(
                slug=slug, finding_type="missing-canonical", scope=scope,
                path=canonical,
                detail="lock entry exists but canonical directory is absent",
                fix_action=None,  # reclone would require source URL access
            ))
            continue

        # 2. Missing content file.
        content_file = canonical / f"{slug}.md"
        if not content_file.exists():
            findings.append(Finding(
                slug=slug, finding_type="missing-content-file", scope=scope,
                path=content_file,
                detail=f"{slug}.md absent in canonical",
                fix_action=None,
            ))

        # 3. Dirty working tree.
        if skill_git.is_git_repo(canonical):
            try:
                wt = skill_git.status(canonical, env=None)
                if wt == skill_git.GitWorkingTreeStatus.DIRTY:
                    findings.append(Finding(
                        slug=slug, finding_type="dirty-canonical", scope=scope,
                        path=canonical,
                        detail="canonical has uncommitted changes",
                        fix_action=None,
                    ))
            except skill_git.GitError:
                pass

        # 4. Standard-slot drift (#361): the .claude/agents/<slug>.md slot
        # exists but differs from the SCOPE-APPROPRIATE canonical. The
        # per-slug `canonical` above is the GLOBAL library; a project slot is
        # seeded from the PROJECT canonical and may legitimately differ from
        # the library — comparing against the wrong baseline would report
        # false drift and the fix would install the wrong version.
        scope_content = canonical_agent_dir(
            slug, scope=scope, home=home, project=project,
        ) / f"{slug}.md"
        slot: Path | None
        try:
            slot = get_adapter("standard").destination(
                slug, scope=scope, home=home, project=project,
            )
        except ValueError:
            slot = None
        if (
            scope_content.exists()
            and slot is not None
            and slot.exists()
            and not filecmp.cmp(scope_content, slot, shallow=False)
        ):
            findings.append(Finding(
                slug=slug, finding_type="standard-slot-drift", scope=scope,
                path=slot,
                detail=(
                    "standard slot differs from the canonical — the file at "
                    f"{slot} may be hand-edited or hand-authored; the fix "
                    "re-seeds it from the canonical and its current content "
                    f"will be DISCARDED (baseline: {scope_content}; inspect "
                    f"first with: diff {slot} {scope_content})"
                ),
                fix_action=FixAction(
                    shell_preview=(
                        f"cp {scope_content} {slot} "
                        f"&& touch {_sentinel_path(slot)}"
                    ),
                    apply=lambda c=scope_content, s=slot: _reseed_slot(c, s),
                ),
            ))

        # 4b. cursor-shadow (#361, spec § Doctor): cursor reads the standard
        # .claude/agents/ dir natively, but its OWN .cursor/agents/<slug>.md
        # WINS name conflicts — a pre-existing cursor projection therefore
        # shadows the standard slot with a divergent copy. ALWAYS report-only
        # (PM review F2): cursor installs go through the symlink adapter,
        # which writes NO ownership sentinel, so a sentinel-gated removal fix
        # could never fire in reality — and the file may equally be
        # user-authored there. Informational (see _INFORMATIONAL_TYPES).
        if scope_content.exists() and slot is not None and slot.exists():
            cursor_dest: Path | None
            try:
                cursor_dest = get_adapter("cursor").destination(
                    slug, scope=scope, home=home, project=project,
                )
            except ValueError:
                cursor_dest = None
            if (
                cursor_dest is not None
                and cursor_dest.exists()
                and not filecmp.cmp(scope_content, cursor_dest, shallow=False)
            ):
                findings.append(Finding(
                    slug=slug, finding_type="cursor-shadow", scope=scope,
                    path=cursor_dest,
                    detail=(
                        "cursor reads its own .cursor/agents first, so this "
                        f"file shadows the standard slot at {slot} — if the "
                        "shadowing is unintended, remove it manually or run "
                        f"`agent uninstall {slug} --harnesses cursor`"
                    ),
                    fix_action=None,
                ))

    # 4.5: unlisted — project lock entry whose slug is missing from the
    # library lock (#360). Inert until #362 lands (the CLI writes no project
    # lock today); ships now for forward-compatibility.
    # Only run when no slug filter is active (sweep run), and only for project
    # scope (the library lock is the global authority; this check is meaningless
    # for global scope). Actionable — NOT in _INFORMATIONAL_TYPES.
    if not slugs and scope == "project":
        lib_slugs = set(read_lock(library_lock_path()).skills)
        for slug, entry in sorted(targets.items()):
            if slug in lib_slugs:
                continue
            findings.append(Finding(
                slug=slug, finding_type="unlisted", scope=scope, path=lock_path,
                detail=(
                    "project lock entry's slug is missing from the library "
                    "lock (install is functional; the library no longer "
                    "tracks it)"
                ),
                fix_action=_make_readd_library_action(slug=slug, entry=entry),
            ))

    # 5. Orphan canonicals — directories under the library base with no lock
    # entry. This catches the #313 class of orphan: a clone left behind by a
    # failed `agent add` (slug mismatch, no --slug) before the lock is written.
    # Only run when no slug filter is active (targeted run won't see orphans)
    # and only for global scope (the library is global-only; project scope has
    # no canonical directory layout to walk).
    if not slugs and scope == "global":
        library_base = library_agent_path("__probe__").parent
        if library_base.is_dir():
            lock_slugs = set(lock.skills.keys())
            for child in sorted(library_base.iterdir()):
                if not child.is_dir():
                    continue
                if child.name not in lock_slugs:
                    orphan = child
                    findings.append(Finding(
                        slug=child.name,
                        finding_type="orphan-canonical",
                        scope=scope,
                        path=orphan,
                        detail="canonical directory has no lock entry",
                        fix_action=FixAction(
                            shell_preview=f"rm -rf {orphan}",
                            apply=lambda p=orphan: shutil.rmtree(p),
                        ),
                    ))

    # 6. Standard-slot sweep (#361, sentinel-aware): .claude/agents/ is the
    # PRIMARY dir where users hand-author Claude Code subagents, so "no lock
    # entry" must NEVER imply an rm fix. The ownership evidence is the .attk
    # sidecar sentinel written by the standard adapter. Only runs when no
    # slug filter is active (a targeted run won't see strays).
    if not slugs:
        agents_dir: Path | None
        try:
            agents_dir = get_adapter("standard").destination(
                "__probe__", scope=scope, home=home, project=project,
            ).parent
        except ValueError:
            agents_dir = None
        if agents_dir is not None and agents_dir.is_dir():
            lock_slugs = set(lock.skills.keys())
            for child in sorted(agents_dir.glob("*.md")):
                if child.stem in lock_slugs:
                    continue
                if _sentinel_path(child).exists():
                    findings.append(Finding(
                        slug=child.stem,
                        finding_type="standard-slot-orphan",
                        scope=scope, path=child,
                        detail=(
                            "tool-written standard slot file (sentinel "
                            "present) has no lock entry"
                        ),
                        fix_action=FixAction(
                            shell_preview=f"rm {child} {_sentinel_path(child)}",
                            apply=lambda p=child: _rm_file_and_sidecar(p),
                        ),
                    ))
                else:
                    findings.append(Finding(
                        slug=child.stem,
                        finding_type="standard-slot-unmanaged",
                        scope=scope, path=child,
                        detail=(
                            f"{child.name} is not managed by "
                            "agent-toolkit-cli (no sentinel, no lock entry) "
                            "— informational only"
                        ),
                        fix_action=None,
                    ))
            for side in sorted(agents_dir.glob(".*.attk")):
                # _sentinel_path convention: <dir>/<name> → <dir>/.<name>.attk,
                # so the slot file is the sidecar name minus the leading dot
                # and the .attk suffix.
                main_file = agents_dir / side.name[1:-len(".attk")]
                if not main_file.exists():
                    findings.append(Finding(
                        slug=main_file.stem,
                        finding_type="standard-slot-dangling-sidecar",
                        scope=scope, path=side,
                        detail=(
                            "ownership sidecar exists but its slot file is "
                            "gone; a stale sidecar would authorize a future "
                            "silent overwrite"
                        ),
                        fix_action=FixAction(
                            shell_preview=f"rm {side}",
                            apply=lambda p=side: p.unlink(),
                        ),
                    ))

    return findings


@click.command("doctor")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--no-fix", is_flag=True, help="Report only; do not prompt or mutate.")
@click.pass_context
def doctor_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
    no_fix: bool,
) -> None:
    """Diagnose agent installation drift.

    Checks for missing canonicals, missing content files, dirty working
    trees, and orphan canonicals, plus the standard .claude/agents slot
    (#361): standard-slot-drift, cursor-shadow (a divergent .cursor/agents
    copy shadowing the slot — informational), standard-slot-orphan,
    standard-slot-unmanaged (hand-authored files — informational), and
    standard-slot-dangling-sidecar. Informational findings are reported but
    never fail the exit code. Reports findings and (unless --no-fix) offers
    to apply automatic repairs where available.
    """
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    findings = _diagnose(
        slugs=slugs or None,
        scope=scope, home=home, project=project_root,
    )

    if not findings:
        click.echo("all clean")
        return

    fixed = skipped = informational = 0
    actionable_total = sum(
        1 for f in findings if f.finding_type not in _INFORMATIONAL_TYPES
    )
    quit_loop = False
    for f in findings:
        click.echo("")
        click.echo(f"{f.slug} · {f.finding_type} ({f.scope})")
        click.echo(f"  path:   {f.path}")
        click.echo(f"  detail: {f.detail}")
        if f.finding_type in _INFORMATIONAL_TYPES:
            # Report-only notice about a file we do not manage — visible,
            # but never fails the exit code or the clean verdict (F1).
            informational += 1
            click.echo("  (informational — no automatic fix)")
            continue
        if f.fix_action is None or no_fix or quit_loop:
            skipped += 1
            if f.fix_action is None:
                click.echo("  (report-only — no automatic fix)")
            continue
        click.echo(f"  fix:    {f.fix_action.shell_preview}")
        try:
            ans = click.prompt(
                "  apply?", default="N", show_default=False,
                type=click.Choice(["y", "N", "q"], case_sensitive=False),
            )
        except (click.Abort, EOFError, OSError):
            click.echo("\n  (no input available — stopping; nothing applied)")
            quit_loop = True
            skipped += 1
            continue
        ans = ans.lower()
        if ans == "y":
            try:
                f.fix_action.apply()
                click.echo("  fixed.")
                fixed += 1
            except Exception as exc:
                click.echo(f"  fix failed: {exc}")
                skipped += 1
        elif ans == "q":
            quit_loop = True
            skipped += 1
        else:
            skipped += 1

    click.echo("")
    parts = f"summary: {len(findings)} findings, {fixed} fixed, {skipped} skipped"
    if informational:
        parts += f", {informational} informational"
    click.echo(parts)
    # Exit semantics consider ACTIONABLE findings only (F1): informational
    # notices never fail doctor, and an informational-only run is clean.
    if actionable_total == 0:
        click.echo(f"all clean ({informational} informational)")
        return
    if skipped > 0 or fixed < actionable_total:
        ctx.exit(1)
