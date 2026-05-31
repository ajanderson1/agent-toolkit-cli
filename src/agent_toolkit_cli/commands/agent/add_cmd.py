"""`agent add <source>` — global-only (mirrors `skill add` / `pi-extension add`).

Clones a git source into the global agent library and writes a lock entry.
No project-scope flag; agents are always added to the global library first,
then installed (projected) into specific harnesses via `agent install`.

Lock is written ONLY after a successful clone (#283 class of bug).
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
from agent_toolkit_cli.agent_paths import library_agent_path, library_lock_path
from agent_toolkit_cli.skill_source import ParsedSource, SourceParseError, parse_source


class AddError(RuntimeError):
    """agent add failed."""


def _derive_slug(parsed: ParsedSource) -> str | None:
    """Derive a default slug from a parsed source (mirrors skill add)."""
    if parsed.owner_repo:
        return parsed.owner_repo.split("/", 1)[1]
    return Path(parsed.url).name or None


@click.command("add", epilog="""\
Examples:

\b
  agent-toolkit-cli agent add ajanderson1/my-agent-skill
  agent-toolkit-cli agent add ajanderson1/my-agent-skill --slug my-agent
  agent-toolkit-cli agent add ajanderson1/my-agent-skill --ref main
""")
@click.argument("source")
@click.option("--slug", default=None, help="Override the derived slug.")
@click.option("--ref", default=None, help="Branch or tag to clone.")
def add_cmd(source: str, slug: str | None, ref: str | None) -> None:
    """Add an agent to the global library (clone + lock entry).

    The agent is not projected to any harness yet. Run `agent install <slug>`
    to create projections.
    """
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise click.ClickException(str(exc)) from exc

    if ref is not None:
        import dataclasses
        parsed = dataclasses.replace(parsed, ref=ref)

    final_slug = slug or _derive_slug(parsed)
    if not final_slug:
        raise click.ClickException(
            f"Cannot derive a slug from {source!r}; pass --slug explicitly"
        )

    lock_path = library_lock_path()
    lock = read_lock(lock_path)

    existing_entry = lock.skills.get(final_slug)
    if existing_entry is not None:
        requested = parsed.owner_repo or parsed.url
        if existing_entry.source != requested:
            raise click.ClickException(
                f"{final_slug}: library entry exists with source "
                f"{existing_entry.source!r}; refusing to overwrite with "
                f"{requested!r}. Run `agent remove {final_slug}` first."
            )
        # Already present with the same source — idempotent.
        click.echo(f"already in library: {final_slug}")
        return

    canonical = library_agent_path(final_slug)
    if not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone(parsed.url, canonical, ref=parsed.ref, env=None)
        except skill_git.GitError as exc:
            raise click.ClickException(f"clone failed: {exc}") from exc

    if skill_git.is_git_repo(canonical):
        try:
            upstream_sha: str | None = skill_git.remote_head_sha(
                canonical, ref=parsed.ref or "main", env=None,
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

    entry = LockEntry(
        source=parsed.owner_repo or parsed.url,
        source_type=parsed.type,
        ref=parsed.ref,
        agent_path=f"{final_slug}.md",
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, final_slug, entry))
    click.echo(f"added {final_slug} to library <- {parsed.url}")
