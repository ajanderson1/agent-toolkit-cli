"""`instructions doctor` — find conflicting/orphan/stray pointers."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import click

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
from agent_toolkit_cli.instructions_lock import read_lock


@dataclass
class FixAction:
    """A repair the user can opt into for a finding."""

    shell_preview: str
    apply: Callable[[], None]


@dataclass
class Finding:
    """One doctor finding. `fix_action=None` means report-only."""

    message: str
    fix_action: "FixAction | None" = None


def _unmanaged_finding(
    *,
    pointer: Path,
    harness: str,
    canonical: Path,
    scope: str,
    project_root: "Path | None",
    home: "Path | None",
    lock_path: Path,
) -> Finding:
    """Build an unmanaged finding. Report-only if canonical already has content."""
    adoptable = not canonical.exists() or canonical.stat().st_size == 0
    if not adoptable:
        return Finding(message=(
            f"unmanaged: real file at {pointer} is not in the lock; "
            f"AGENTS.md already exists — adopt skipped (content merge is out of scope)"
        ))
    return Finding(message=(
        f"unmanaged: real file at {pointer} is not in the lock "
        f"(adopt → rename to AGENTS.md + symlink {pointer.name})"
    ))


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
    for f in findings:
        click.echo(f.message)
    ctx.exit(1)
