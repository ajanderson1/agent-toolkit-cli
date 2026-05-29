"""`instructions doctor` — find conflicting/orphan/stray pointers."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
from agent_toolkit_cli.instructions_lock import read_lock


@click.command(help="Find conflicting/orphan/stray pointers vs the lock.")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
)
@click.pass_context
def doctor_cmd(ctx: click.Context, scope: str) -> None:
    project_root: Path | None = None
    home: Path | None = None
    if scope == "project":
        obj = ctx.find_root().params.get("project_root")
        project_root = obj if obj else Path.cwd()
        canonical = instructions_paths.project_canonical_agents_md(project_root)
    else:
        home = Path.home()
        canonical = instructions_paths.global_canonical_agents_md()

    findings: list[str] = []

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
        findings.append(f"orphan: canonical AGENTS.md missing at {canonical}")

    # Conflict: lock says ON but pointer is a real file or points elsewhere.
    for harness in sorted(wanted):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if pointer.exists() and not pointer.is_symlink():
            findings.append(
                f"conflict: {harness} pointer at {pointer} is a real file (not ours)"
            )
        elif pointer.is_symlink() and pointer.resolve() != canonical.resolve():
            findings.append(
                f"conflict: {harness} pointer at {pointer} → {pointer.resolve()} (not canonical)"
            )

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
            findings.append(
                f"stray: {harness} pointer at {pointer} points at canonical "
                "but isn't recorded in the lock"
            )

    if not findings:
        click.echo("clean — no findings at this scope")
        return
    for f in findings:
        click.echo(f)
    ctx.exit(1)
