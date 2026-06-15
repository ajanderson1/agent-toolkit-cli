"""`pi-extension update [slugs] [-g/-p]` — fetch + merge upstream for store-owned extensions.

npm rows have no upstream git repo; they are skipped with an informational message.
Mirrors skill update_cmd (minus monorepo / copy-mode paths — pi-extension has
neither). Lock is updated after a successful merge.
"""
from __future__ import annotations

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.commands.pi_extension._common import (
    scope_and_roots,
    scope_banner,
)
from agent_toolkit_cli.pi_extension_lock import read_lock, write_lock
from agent_toolkit_cli.pi_extension_paths import (
    library_pi_extension_path,
    lock_file_path,
)


@click.command("update", epilog="""\
Examples:

\b
  agent-toolkit-cli pi-extension update              # update all extensions
  agent-toolkit-cli pi-extension update my-ext       # update one extension
""")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def update_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
) -> None:
    """Fetch + merge upstream for each store-owned extension."""
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))
    targets = slugs or tuple(sorted(lock.skills))
    had_error = False

    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_error = True
            continue

        entry = lock.skills[slug]

        if entry.source_type == "npm":
            click.echo(f"{slug}: npm row — no upstream git repo; no-op")
            continue

        canonical = library_pi_extension_path(slug)
        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: copy-mode (no .git/) — cannot update; remove and "
                f"re-add to switch to git-managed"
            )
            had_error = True
            continue

        if entry.ref_looks_pinned:
            click.echo(
                f"{slug}: pinned to {entry.ref[:7]} — skipping "
                f"(remove and re-add to change the pin)"
            )
            continue

        ref = skill_git.resolve_ref(entry.ref, canonical)
        skill_git.fetch(canonical, env=None)
        try:
            skill_git.merge(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            click.echo(
                f"{slug}: conflict during merge (resolve in working copy)"
            )
            click.echo(exc.stderr)
            had_error = True
            continue

        entry.local_sha = skill_git.head_sha(canonical, env=None)
        try:
            entry.upstream_sha = skill_git.remote_head_sha(
                canonical, ref=ref, env=None,
            )
        except skill_git.GitError:
            pass  # remote ref missing; keep old upstream_sha
        # Memoise the detected default branch (parity with skill update) so the
        # next run reads it from the lock instead of re-detecting. Merge-success
        # path only, so always a real, mergeable branch.
        if entry.ref is None:
            entry.ref = ref
        write_lock(lock_path, lock)
        click.echo(f"{slug}: updated")

    if had_error:
        ctx.exit(1)
