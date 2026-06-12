"""`agent add <source>` — global-only (mirrors `skill add` / `pi-extension add`).

Clones a git source into the global agent library and writes a lock entry.
No project-scope flag; agents are always added to the global library first,
then installed (projected) into specific harnesses via `agent install`.

Two source shapes, mirroring `skill add`:

- **Single-repo** (`<owner>/<repo>`) — the whole repo IS one agent, with
  `<slug>.md` at the repo root; slug defaults to the repo name. The repo is
  cloned directly as the library canonical and is writable (push lands on its
  own remote).
- **Category-repo / monorepo** (`<owner>/<repo>/<subpath>`) — many agents in
  one repo, each in its own directory `<subpath>/<slug>.md`. The repo is
  cloned ONCE as a shared parent cache under the agent tree, and the library
  canonical is a symlink into `<parent>/<subpath>`. Pinned to parent HEAD;
  read-only (no per-agent remote to push to).

Lock is written ONLY after a successful clone (#283 class of bug).
"""
from __future__ import annotations

import dataclasses
import shutil
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
    agent_parent_clone_path,
    library_agent_path,
    library_lock_path,
)
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
  # Single-repo agent (whole repo is one agent, <slug>.md at root)
  agent-toolkit-cli agent add ajanderson1/my-agent-skill
  agent-toolkit-cli agent add ajanderson1/my-agent-skill --slug my-agent
  agent-toolkit-cli agent add ajanderson1/my-agent-skill --ref main

\b
  # Category-repo agent (many agents per repo, addressed by subpath)
  agent-toolkit-cli agent add ajanderson1/agents-workflow/project-manager
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
        parsed = dataclasses.replace(parsed, ref=ref)

    if parsed.subpath:
        _add_monorepo(parsed, slug)
    else:
        _add_single(parsed, slug)


def _add_single(parsed: ParsedSource, slug: str | None) -> None:
    """Single-repo add: clone the whole repo as the canonical (current model)."""
    final_slug = slug or _derive_slug(parsed)
    if not final_slug:
        raise click.ClickException(
            f"Cannot derive a slug from {parsed.url!r}; pass --slug explicitly"
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
    fresh_clone = False
    if not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone_pinned_or_branch(
                parsed.url, canonical, ref=parsed.ref, env=None,
            )
        except skill_git.GitError as exc:
            raise click.ClickException(f"clone failed: {exc}") from exc
        fresh_clone = True

    # Fail loud at add time if the content file the lock will point at is absent
    # (#304 bug 2 / #283 lock-honesty class). Without this, `add` writes a lock
    # entry asserting `<slug>.md` exists, then `install` silently no-ops while
    # printing success. The clone stays on disk — a re-run with a `--slug` that
    # matches the source's content file is idempotent via the `exists()` guard
    # above. Mirrors doctor's `missing-content-file` check.
    #
    # #313 cleanup: if *this invocation* created the canonical (fresh_clone)
    # and the content-file check fails, remove the just-created clone so we
    # don't leave an unreclaimable orphan. Only fires for a fresh clone — a
    # pre-existing canonical (idempotent re-run with correct --slug) is left
    # alone.
    content_file = canonical / f"{final_slug}.md"
    if not content_file.exists():
        if fresh_clone:
            shutil.rmtree(canonical, ignore_errors=True)
        raise click.ClickException(
            f"{final_slug}: content file {final_slug}.md absent in source "
            f"{parsed.url!r}; expected <slug>.md at the repo root. "
            f"Pass --slug to match the source's content file."
        )

    if skill_git.is_git_repo(canonical):
        try:
            upstream_sha: str | None = skill_git.remote_head_sha(
                canonical,
                ref=skill_git.resolve_ref(parsed.ref, canonical),
                env=None,
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


def _add_monorepo(parsed: ParsedSource, slug: str | None) -> None:
    """Category-repo add: clone the parent once, symlink the agent subdir in.

    Mirrors `commands/skill/__init__.py:_add_monorepo`. The agent lives at
    `<subpath>/<slug>.md` (directory form), so the library canonical symlinks
    at `<parent>/<subpath>` and `<canonical>/<slug>.md` resolves the content
    file — keeping `agent_install`'s `canonical / <slug>.md` convention intact.
    """
    from agent_toolkit_cli._install_core import _symlink_or_copy

    if parsed.owner_repo is None:
        raise click.UsageError("monorepo source must resolve to owner/repo")
    owner, repo = parsed.owner_repo.split("/", 1)
    subpath = parsed.subpath
    assert subpath is not None  # add_cmd only routes here when subpath is set
    # The agent slug is the LAST segment of the subpath (its directory name),
    # not the repo name. `--slug` overrides for the rare rename case.
    final_slug = slug or Path(subpath).name

    parent_dir = agent_parent_clone_path(owner, repo, ref=parsed.ref, env=None)
    if not parent_dir.exists():
        parent_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone_pinned_or_branch(
                parsed.url, parent_dir, ref=parsed.ref, env=None,
            )
        except Exception as exc:
            raise click.ClickException(f"parent clone failed: {exc}") from exc
    else:
        # Refresh the shared parent cache so a *growing* category repo resolves
        # agents added after this cache was first cloned (#276 class). fetch
        # alone advances the remote-tracking ref but leaves the working tree
        # pinned; the hard reset moves it onto the new tip. The parent is a
        # read-only cache, so the reset is safe. NEVER rmtree it — it is shared
        # across every agent from this repo (unlike the single-repo fresh-clone
        # cleanup, which owns its whole clone).
        ref = skill_git.resolve_ref(parsed.ref, parent_dir)
        try:
            skill_git.fetch_ref(parent_dir, ref=ref, env=None)
            skill_git.reset_hard(parent_dir, ref=ref, env=None)
        except Exception as exc:
            click.echo(
                f"warning: parent refresh failed for {parent_dir}: {exc}",
                err=True,
            )

    agent_root = parent_dir / subpath
    content_rel = f"{subpath}/{final_slug}.md"
    if not (agent_root / f"{final_slug}.md").exists():
        # Do NOT rmtree the shared parent on a missing content file.
        raise click.ClickException(
            f"{final_slug}: content file {content_rel} not found in parent "
            f"{parsed.owner_repo}; expected <subpath>/<slug>.md."
        )

    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    existing_entry = lock.skills.get(final_slug)
    if existing_entry is not None:
        requested = parsed.owner_repo
        if (existing_entry.source != requested
                or existing_entry.agent_path != content_rel):
            raise click.ClickException(
                f"{final_slug}: library entry exists with source "
                f"{existing_entry.source!r} agentPath="
                f"{existing_entry.agent_path!r}; refusing to overwrite with "
                f"{requested!r} agentPath={content_rel!r}. "
                f"Run `agent remove {final_slug}` first."
            )
        click.echo(f"already in library: {final_slug}")
        return

    library_dir = library_agent_path(final_slug)
    materialised = "symlink"
    if not library_dir.exists() and not library_dir.is_symlink():
        materialised = _symlink_or_copy(agent_root, library_dir)

    parent_sha = (
        skill_git.head_sha(parent_dir, env=None)
        if skill_git.is_git_repo(parent_dir) else None
    )
    entry = LockEntry(
        source=parsed.owner_repo,
        source_type=parsed.type,
        ref=parsed.ref,
        agent_path=content_rel,
        upstream_sha=parent_sha,
        local_sha=None,
        parent_url=parsed.url,
        read_only=True,
        extras={"materialised": materialised} if materialised == "copy" else {},
    )
    write_lock(lock_path, add_entry(lock, final_slug, entry))
    click.echo(f"added {final_slug} to library <- {parsed.url}/{subpath}")
