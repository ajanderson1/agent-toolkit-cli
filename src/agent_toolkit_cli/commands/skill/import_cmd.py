"""`skill import <file>` — reconstruct the global library from a lock file.

Additive merge: only slugs absent locally are added (skip-if-exists is total).
By default each added skill is pinned to the lock's recorded upstream SHA;
--latest clones every new skill at its ref's current HEAD instead. Per-skill
clone failures are non-fatal (partial success); exit code is 1 if any failed.
The export artifact is just another machine's global skills-lock.json — there
is no `export` command.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.skill_lock import (
    LockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.skill_paths import library_lock_path
from agent_toolkit_cli.skill_source import ParsedSource


_NOTES = (
    "  • Imported skills are pinned to upstream commits. Local commits or\n"
    "    uncommitted changes on the source machine are NOT reflected.",
    "  • Global-library skills only. Project-scoped skills (per-project\n"
    "    skills-lock.json) must be re-installed manually in each project.",
    "  • Skills were added to the library but not installed for any agent.\n"
    "    Run `skill install <slug> --agents ...` to make them visible.",
)


def _print_notes() -> None:
    click.echo("\nNotes:")
    for note in _NOTES:
        click.echo(note)


def _entry_to_parsed(entry: LockEntry) -> ParsedSource:
    """Map a lock entry back to a ParsedSource the reconstruction helper accepts.

    A monorepo entry carries a directory skillPath (not "SKILL.md"), a
    parent_url, and read_only=True; its skillPath IS the subpath. A single
    entry's skillPath is "SKILL.md" and has no subpath.
    """
    from agent_toolkit_cli.skill_lock import clone_url_from_entry

    is_monorepo = bool(entry.parent_url) or (
        entry.skill_path not in (None, "SKILL.md")
    )
    if is_monorepo and entry.parent_url:
        url = entry.parent_url
    else:
        url = clone_url_from_entry(entry)
    subpath = entry.skill_path if is_monorepo else None
    return ParsedSource(
        type=entry.source_type or "git",
        url=url,
        owner_repo=entry.source if "/" in entry.source else None,
        ref=entry.ref,
        subpath=subpath,
    )


@click.command("import", epilog="""\
Examples:

\b
  agent-toolkit-cli skill import ~/sync/skills-lock.json
  agent-toolkit-cli skill import ~/sync/skills-lock.json --latest
""")
@click.argument("file", type=click.Path(path_type=Path), required=True)
@click.option("--latest", is_flag=True,
              help="Clone each new skill at its ref's current HEAD "
                   "instead of the recorded SHA.")
@click.pass_context
def import_cmd(ctx: click.Context, file: Path, latest: bool) -> None:
    """Add skills from another machine's lock FILE into the global library."""
    if not file.exists():
        raise click.UsageError(f"import file not found: {file}")

    incoming = read_lock(file)
    current = read_lock(library_lock_path())

    n = len(incoming.skills)
    click.echo(f"importing from {file} ({n} skill{'s' if n != 1 else ''})\n")

    added: list[tuple[str, str | None, bool]] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    from agent_toolkit_cli.commands.skill import reconstruct_skill_into_library

    for slug in sorted(incoming.skills):
        entry = incoming.skills[slug]
        if slug in current.skills:
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (already present)")
            continue

        parsed = _entry_to_parsed(entry)
        pin_sha = None if latest else entry.upstream_sha
        try:
            up_sha, local_sha = reconstruct_skill_into_library(
                parsed, slug, pin_sha=pin_sha,
            )
        except Exception as exc:  # noqa: BLE001 — report, don't abort
            failed.append((slug, str(exc)))
            click.echo(f"  failed   {slug}  ({exc})")
            continue

        new_entry = LockEntry(
            source=entry.source,
            source_type=entry.source_type,
            ref=entry.ref,
            skill_path=entry.skill_path,
            upstream_sha=up_sha,
            local_sha=local_sha,
            parent_url=entry.parent_url,
            read_only=entry.read_only,
            extras=dict(entry.extras) if entry.read_only else {},
        )
        current = add_entry(current, slug, new_entry)
        landed = (local_sha or up_sha or "")[:7]
        suffix = f"(latest: {landed})" if latest else f"@ {landed}"
        click.echo(f"  added    {slug}  <- {entry.source} {suffix}")
        added.append((slug, landed, latest))

    if added:
        write_lock(library_lock_path(), current)

    click.echo(
        f"\nsummary: {len(added)} added, {len(skipped)} skipped, "
        f"{len(failed)} failed"
    )
    _print_notes()
    if failed:
        ctx.exit(1)
