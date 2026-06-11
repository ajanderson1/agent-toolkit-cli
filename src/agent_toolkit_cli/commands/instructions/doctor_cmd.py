"""`instructions doctor` — find conflicting/orphan/stray pointers."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import click

from agent_toolkit_cli import instructions_install, instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    Scope,
    add_entry,
    read_lock,
    write_lock,
)


@dataclass
class FixAction:
    """A repair the user can opt into for a finding."""

    shell_preview: str
    apply: Callable[[], None]


@dataclass
class Finding:
    """One doctor finding. `fix_action=None` means report-only."""

    message: str
    fix_action: FixAction | None = None


def _adopt_harness_for(
    pointer: Path,
    harness: str,
    *,
    scope: str,
    project_root: Path | None,
    home: Path | None,
) -> str:
    """Derive the canonical adopting harness for a slot.

    At project scope, augment + claude-code physically *share* one path
    ({PROJECT}/CLAUDE.md); claude-code is the canonical adopter for that shared
    slot. The match must be by path, not by filename: at global scope the slots
    are distinct (~/.augment/CLAUDE.md vs ~/.claude/CLAUDE.md) yet both named
    CLAUDE.md, so a name check would misadopt augment's own global file as
    claude-code. Otherwise the scanning harness owns its slot.
    """
    try:
        claude_slot = _pointer_path("claude-code", scope, project_root, home)
    except ValueError:
        claude_slot = None
    if claude_slot is not None and pointer == claude_slot:
        return "claude-code"
    return harness


def _backup_then_symlink_finding(
    *,
    pointer: Path,
    harness: str,
    canonical: Path,
    scope: str,
    project_root: Path | None,
    home: Path | None,
    lock_path: Path,
) -> Finding:
    """Canonical AGENTS.md already has content: offer to back the unmanaged
    file up beside itself and point its slot at canonical. Content is never
    merged — the .bak keeps the user's text for manual reconciliation (#375).
    """
    backup = pointer.with_name(pointer.name + ".pre-adopt.bak")
    adopt_harness = _adopt_harness_for(
        pointer, harness, scope=scope, project_root=project_root, home=home,
    )

    def _apply() -> None:
        # Re-assert guards at apply time — state may have changed since the
        # scan. is_symlink() catches a dangling symlink (exists() is False but
        # rename() onto it would still replace it).
        if backup.exists() or backup.is_symlink():
            raise click.ClickException(
                f"{backup} already exists — refusing to overwrite a previous backup"
            )
        if not canonical.exists() or canonical.stat().st_size == 0:
            raise click.ClickException(
                f"{canonical} no longer has content — re-run doctor"
            )
        prior = read_lock(lock_path)
        prior_existed = lock_path.exists()
        # Rename BEFORE writing the lock so a failure never leaves a lying
        # lock. The try opens HERE — not after write_lock — so a lock-write
        # failure also rolls the rename back; otherwise the user's file would
        # be stranded at the .bak with an empty slot, a state a doctor re-run
        # reports as clean (critical-review finding, #375).
        pointer.rename(backup)
        try:
            existing = prior.instructions.get("AGENTS.md")
            new_harnesses = sorted({*(existing.harnesses if existing else []), adopt_harness})
            new = add_entry(prior, "AGENTS.md", InstructionsLockEntry(
                scope=cast("Scope", scope),
                source="AGENTS.md",
                harnesses=new_harnesses,
            ))
            write_lock(lock_path, new)
            instructions_install.apply(
                scope=cast("Scope", scope), project_root=project_root, home=home,
            )
        except Exception as exc:
            # Stronger than the adopt fix's contract: roll back on ANY failure
            # after the rename (lock write or apply). Drop any symlink apply()
            # laid at our slot, restore the user's file from the backup, then
            # restore the prior lock.
            if pointer.is_symlink():
                pointer.unlink()
            if backup.exists() and not pointer.exists():
                backup.rename(pointer)
            if prior_existed:
                write_lock(lock_path, prior)
            else:
                lock_path.unlink(missing_ok=True)
            raise click.ClickException(str(exc)) from exc

    return Finding(
        message=(
            f"unmanaged: real file at {pointer} is not in the lock; "
            f"AGENTS.md already has content — fix backs the file up to "
            f"{backup.name} (content is never merged; reconcile manually)"
        ),
        fix_action=FixAction(
            shell_preview=(
                f"mv {pointer.name} {backup.name} && "
                f"instructions install --scope {scope} --harness {adopt_harness}"
            ),
            apply=_apply,
        ),
    )


def _unmanaged_finding(
    *,
    pointer: Path,
    harness: str,
    canonical: Path,
    scope: str,
    project_root: Path | None,
    home: Path | None,
    lock_path: Path,
) -> Finding:
    """Build an unmanaged finding. Dispatches on canonical state: missing/empty
    → adopt fix (rename to canonical); populated → backup-then-symlink fix."""
    adoptable = not canonical.exists() or canonical.stat().st_size == 0
    if not adoptable:
        return _backup_then_symlink_finding(
            pointer=pointer, harness=harness, canonical=canonical,
            scope=scope, project_root=project_root, home=home,
            lock_path=lock_path,
        )

    adopt_harness = _adopt_harness_for(
        pointer, harness, scope=scope, project_root=project_root, home=home,
    )

    def _apply() -> None:
        # Re-assert the guard (a non-empty AGENTS.md may have appeared).
        if canonical.exists() and canonical.stat().st_size > 0:
            raise click.ClickException(
                f"{canonical} already exists with content — refusing to clobber"
            )
        prior = read_lock(lock_path)
        prior_existed = lock_path.exists()
        # Rename BEFORE writing the lock so a failure never leaves a lying lock.
        pointer.rename(canonical)
        existing = prior.instructions.get("AGENTS.md")
        new_harnesses = sorted({*(existing.harnesses if existing else []), adopt_harness})
        new = add_entry(prior, "AGENTS.md", InstructionsLockEntry(
            scope=cast("Scope", scope),
            source="AGENTS.md",
            harnesses=new_harnesses,
        ))
        write_lock(lock_path, new)
        try:
            instructions_install.apply(scope=scope, project_root=project_root, home=home)
        except Exception as exc:
            # Roll back on ANY failure — not just the two domain errors. apply()
            # can fail on perms/ENOSPC, or succeed on the adopted slot then raise
            # on a *different* wanted slot (leaving a symlink it created). Undo
            # everything: drop any symlink apply() laid at our slot, restore the
            # user's real file, then restore the prior lock. Never leave AGENTS.md
            # renamed + lock written with the slot un-pointed (a lying lock).
            if pointer.is_symlink():
                pointer.unlink()
            if canonical.exists() and not pointer.exists():
                canonical.rename(pointer)
            if prior_existed:
                write_lock(lock_path, prior)
            else:
                lock_path.unlink(missing_ok=True)
            raise click.ClickException(str(exc)) from exc

    return Finding(
        message=f"unmanaged: real file at {pointer} is not in the lock",
        fix_action=FixAction(
            shell_preview=(
                f"mv {pointer.name} AGENTS.md && "
                f"instructions install --harness {adopt_harness}"
            ),
            apply=_apply,
        ),
    )


@click.command(help="Find conflicting/orphan/stray pointers vs the lock.")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
)
@click.option("--no-fix", is_flag=True, help="Report only; do not prompt or mutate.")
@click.pass_context
def doctor_cmd(ctx: click.Context, scope: str, no_fix: bool) -> None:
    project_root: Path | None = None
    home: Path | None = None
    if scope == "project":
        obj = ctx.find_root().params.get("project_root")
        project_root = obj if obj else Path.cwd()
        canonical = instructions_paths.project_canonical_agents_md(project_root)
    else:
        home = Path.home()
        canonical = instructions_paths.global_canonical_agents_md()

    findings: list[Finding] = []
    conflict_paths: set[Path] = set()

    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)
    wanted: set[str] = set()
    for entry in lock.instructions.values():
        wanted.update(h for h in entry.harnesses if h in SUPPORTED_HARNESSES)

    # Pointer slots claimed by a wanted harness — some harnesses share a slot
    # (e.g. `augment` and `claude-code` both use project-root CLAUDE.md), so a
    # symlink at a shared slot is not "stray" if any wanted harness claims it.
    wanted_paths: set[Path] = set()
    for harness in wanted:
        try:
            wanted_paths.add(_pointer_path(harness, scope, project_root, home))
        except ValueError:
            continue

    # Orphan: lock says ON but canonical is gone.
    if wanted and not canonical.exists():
        findings.append(Finding(message=f"orphan: canonical AGENTS.md missing at {canonical}"))

    # Conflict: lock says ON but pointer is a real file or points elsewhere.
    for harness in sorted(wanted):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if pointer.exists() and not pointer.is_symlink():
            conflict_paths.add(pointer)
            findings.append(Finding(
                message=f"conflict: {harness} pointer at {pointer} is a real file (not ours)"
            ))
        elif pointer.is_symlink() and pointer.resolve() != canonical.resolve():
            findings.append(Finding(
                message=f"conflict: {harness} pointer at {pointer} → {pointer.resolve()} (not canonical)"
            ))

    # Stray: a pointer-shaped symlink at a harness slot, pointing at canonical,
    # but not recorded in the lock. (Manual mkdir + ln scenario.) Skip slots that
    # a still-wanted harness shares — they are owned, not stray.
    for harness in sorted(SUPPORTED_HARNESSES - wanted):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if pointer in wanted_paths:
            continue
        if (
            pointer.is_symlink()
            and pointer.resolve() == canonical.resolve()
        ):
            findings.append(Finding(
                message=(
                    f"stray: {harness} pointer at {pointer} points at canonical "
                    "but isn't recorded in the lock"
                )
            ))

    # Unmanaged: a real file (not a symlink) at a known pointer slot that the
    # lock doesn't record. A real file at a *wanted* slot is already a conflict
    # (above), so exclude conflict_paths. Several harnesses share a slot
    # (augment+claude-code → CLAUDE.md); dedupe by path so we emit one finding.
    seen_unmanaged: set[Path] = set()
    for harness in sorted(SUPPORTED_HARNESSES):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if pointer in conflict_paths or pointer in seen_unmanaged:
            continue
        if pointer.exists() and not pointer.is_symlink():
            seen_unmanaged.add(pointer)
            findings.append(_unmanaged_finding(
                pointer=pointer, harness=harness, canonical=canonical,
                scope=scope, project_root=project_root, home=home,
                lock_path=lock_path,
            ))

    if not findings:
        click.echo("clean — no findings at this scope")
        return

    fixed = skipped = 0
    quit_loop = False
    for f in findings:
        click.echo("")
        click.echo(f.message)
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
                click.echo("  adopted.")
                fixed += 1
            except Exception as exc:
                click.echo(f"  adopt failed: {exc}")
                skipped += 1
        elif ans == "q":
            quit_loop = True
            skipped += 1
        else:
            skipped += 1

    click.echo("")
    click.echo(f"summary: {len(findings)} findings, {fixed} fixed, {skipped} skipped")
    if skipped > 0:
        ctx.exit(1)
