"""`pi-extension import <file>` — reconstruct the global library from a lock file.

Additive merge: only slugs absent locally are added (skip-if-exists). Per-slug
clone failures are non-fatal; exit code is 1 if any failed.

extensions[] OBSERVE-ONLY guarantee: this command reads extensions[] (via the
inventory reader) but NEVER adds, removes, or edits any entry in extensions[].
The only config write this command makes is to the pi-extensions-lock.json lock
file and (for store-owned clones) the on-disk store copy.

Fact-check finding (0.77.0 package-manager.js):
  extensions[] is an OVERRIDE-FILTER (not a path-list). isEnabledByOverrides()
  uses settings.json extensions[] as a filter over auto-discovered paths in
  ~/.pi/agent/extensions/ — patterns: plain = include-filter, ! = exclude,
  + = force-include, - = force-exclude. This matches the #109 reading, not the
  v3.2.0 design's path-list claim. Classifier: we do NOT create rows from
  extensions[]. Store-owned entries project via symlink into extensions/; the
  extensions[] array is left strictly observe-only.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.pi_extension_paths import (
    library_lock_path,
    library_pi_extension_path,
)


_NOTES = (
    "  Extensions are added to the library but not installed for any scope.\n"
    "    Run `pi-extension install <slug> -g` to project them.",
    "  Global-library extensions only. Project-scope extensions\n"
    "    (per-project pi-extensions-lock.json) must be re-installed manually.",
)


def _print_notes() -> None:
    click.echo("\nNotes:")
    for note in _NOTES:
        click.echo(note)


@click.command("import", epilog="""\
Examples:

\b
  agent-toolkit-cli pi-extension import ~/sync/pi-extensions-lock.json
  agent-toolkit-cli pi-extension import ~/sync/pi-extensions-lock.json --latest
""")
@click.argument("file", type=click.Path(path_type=Path), required=True)
@click.option("--latest", is_flag=True,
              help="Clone each new extension at its ref's current HEAD "
                   "instead of the recorded SHA.")
@click.pass_context
def import_cmd(ctx: click.Context, file: Path, latest: bool) -> None:
    """Add extensions from another machine's lock FILE into the global library."""
    if not file.exists():
        raise click.UsageError(f"import file not found: {file}")

    incoming = read_lock(file)
    current = read_lock(library_lock_path(env={}))

    n = len(incoming.skills)
    click.echo(f"importing from {file} ({n} extension{'s' if n != 1 else ''})\n")

    added: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    for slug in sorted(incoming.skills):
        entry = incoming.skills[slug]

        if slug in current.skills:
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (already present)")
            continue

        if entry.source_type == "npm":
            # npm row: just record the lock entry, no clone needed.
            new_entry = LockEntry(
                source=entry.source,
                source_type="npm",
                ref=entry.ref,
                pi_extension_path=None,
            )
            current = add_entry(current, slug, new_entry)
            write_lock(library_lock_path(env={}), current)
            click.echo(f"  added    {slug}  (npm: {entry.source})")
            added.append(slug)
            continue

        # Store-owned: clone into the library.
        canonical = library_pi_extension_path(slug, env={})
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
                        canonical, ref=ref or "main", env=None,
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
            pi_extension_path=slug,
            upstream_sha=upstream_sha,
            local_sha=local_sha,
        )
        current = add_entry(current, slug, new_entry)
        # Persist after EACH added extension (same as skill import: a ^C mid-run
        # leaves the lock reflecting exactly what landed on disk).
        write_lock(library_lock_path(env={}), current)
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
