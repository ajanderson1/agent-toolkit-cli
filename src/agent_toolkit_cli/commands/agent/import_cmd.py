"""`agent import <file>` — reconstruct the global library from a lock file.

Additive merge: only slugs absent locally are added (skip-if-exists). Per-slug
clone failures are non-fatal; exit code is 1 if any failed.

Lock is written ONLY after a successful clone (lock honesty, #283 class of bug).
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.agent_lock import (
    LockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.agent_paths import (
    library_agent_path,
    library_lock_path,
)


_NOTES = (
    "  Agents are added to the library but not installed for any harness.\n"
    "    Run `agent install <slug> -g` to project them.",
    "  Global-library agents only. Project-scope agents\n"
    "    (per-project agents-lock.json) must be re-installed manually.",
)


def _print_notes() -> None:
    click.echo("\nNotes:")
    for note in _NOTES:
        click.echo(note)


@click.command("import", epilog="""\
Examples:

\b
  agent-toolkit-cli agent import ~/sync/agents-lock.json
  agent-toolkit-cli agent import ~/sync/agents-lock.json --latest
""")
@click.argument("file", type=click.Path(path_type=Path), required=True)
@click.option("--latest", is_flag=True,
              help="Clone each new agent at its ref's current HEAD "
                   "instead of the recorded SHA.")
@click.pass_context
def import_cmd(ctx: click.Context, file: Path, latest: bool) -> None:
    """Add agents from another machine's lock FILE into the global library."""
    if not file.exists():
        raise click.UsageError(f"import file not found: {file}")

    incoming = read_lock(file)
    current = read_lock(library_lock_path())

    n = len(incoming.skills)
    click.echo(f"importing from {file} ({n} agent{'s' if n != 1 else ''})\n")

    added: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    for slug in sorted(incoming.skills):
        entry = incoming.skills[slug]

        if slug in current.skills:
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (already present)")
            continue

        canonical = library_agent_path(slug)
        if canonical.exists():
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (store copy already exists)")
            continue

        source_url = entry.source
        ref = entry.ref
        pin_sha = None if latest else entry.upstream_sha

        try:
            canonical.parent.mkdir(parents=True, exist_ok=True)
            skill_git.clone(source_url, canonical, ref=ref, env=None, depth=1)

            if pin_sha and skill_git.is_git_repo(canonical):
                try:
                    skill_git.fetch_ref(canonical, ref=pin_sha, env=None, depth=1)
                    skill_git.checkout(canonical, ref=pin_sha, env=None)
                except skill_git.GitError:
                    pass  # pin not available; stay at HEAD

            if skill_git.is_git_repo(canonical):
                try:
                    upstream_sha: str | None = skill_git.remote_head_sha(
                        canonical, ref=skill_git.resolve_ref(ref, canonical), env=None,
                    )
                except skill_git.GitError:
                    upstream_sha = None
                try:
                    local_sha: str | None = skill_git.head_sha(canonical, env=None)
                except skill_git.GitError:
                    local_sha = None
            else:
                upstream_sha = None
                local_sha = None

        except Exception as exc:  # noqa: BLE001 — report, don't abort
            failed.append((slug, str(exc)))
            click.echo(f"  failed   {slug}  ({exc})")
            # Lock honesty (#283): never write a lock entry for a failed clone.
            if canonical.exists():
                import shutil
                shutil.rmtree(canonical, ignore_errors=True)
            continue

        new_entry = LockEntry(
            source=entry.source,
            source_type=entry.source_type,
            ref=entry.ref,
            agent_path=entry.agent_path or f"{slug}.md",
            upstream_sha=upstream_sha,
            local_sha=local_sha,
        )
        current = add_entry(current, slug, new_entry)
        # Persist after EACH added agent (a ^C mid-run leaves the lock
        # reflecting exactly what landed on disk — same as skill/pi-extension import).
        write_lock(library_lock_path(), current)
        landed = (local_sha or upstream_sha or "")[:7]
        suffix = f"(latest: {landed})" if latest else f"@ {landed}"
        click.echo(f"  added    {slug}  <- {entry.source} {suffix}")
        added.append(slug)

    click.echo(
        f"\nsummary: {len(added)} added, {len(skipped)} skipped, "
        f"{len(failed)} failed"
    )
    _print_notes()
    if failed:
        ctx.exit(1)
