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
    checked_agent_content,
    registered_agent_paths, refresh_agent_repo, acquire_agent_parent, validate_agent_revision,
    library_agent_path,
    library_lock_path,
)
from agent_toolkit_cli.skill_source import (
    ParsedSource,
    SourceParseError,
    parse_source,
    sanitize_ref,
)


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
        try:
            ref = sanitize_ref(ref)
        except SourceParseError as exc:
            raise click.ClickException(str(exc)) from exc
        parsed = dataclasses.replace(parsed, ref=ref)

    if parsed.subpath:
        _add_monorepo(parsed, slug)
    else:
        _add_single(parsed, slug)


def _add_single(parsed: ParsedSource, slug: str | None, *, expected_entry_file: str | None = None) -> None:
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
        requested = parsed.identity
        if existing_entry.source != requested or existing_entry.ref != parsed.ref:
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
    if (canonical.exists() or canonical.is_symlink()) and (
        canonical.is_symlink() or not skill_git.is_git_repo(canonical)
        or not skill_git.remote_matches(canonical, parsed.url, None)
    ):
        raise click.ClickException(f"{final_slug}: cannot prove canonical source ownership")
    if not canonical.exists():
        try:
            acquire_agent_parent(canonical,
                lambda stage: skill_git.clone_pinned_or_branch(parsed.url, stage, ref=parsed.ref, env=None),
                registered_agent_paths(canonical, library=lock), new_agent=(final_slug, ""))
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
    # Existing flat packages often carry repository-maintenance AGENTS.md.
    # Prefer the actual flat entry when present; directory packages have only
    # AGENTS.md and record that choice explicitly.
    content_file = canonical / (f"{final_slug}.md" if (canonical / f"{final_slug}.md").is_file() else "AGENTS.md")
    if expected_entry_file is not None and content_file.name != expected_entry_file:
        if fresh_clone:
            shutil.rmtree(canonical, ignore_errors=True)
        raise click.ClickException(f"{final_slug}: source agent shape does not match catalog entryFile")
    if not content_file.exists():
        if fresh_clone:
            shutil.rmtree(canonical, ignore_errors=True)
        raise click.ClickException(
            f"{final_slug}: content file {final_slug}.md absent in source "
            f"{parsed.url!r}; expected <slug>.md at the repo root. "
            f"Pass --slug to match the source's content file."
        )

    try:
        checked_agent_content(canonical, content_file.name, final_slug)
    except Exception as exc:
        if fresh_clone:
            shutil.rmtree(canonical)
        raise click.ClickException(str(exc)) from exc

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
        source=parsed.identity,
        source_type=parsed.type,
        ref=parsed.ref,
        agent_path=content_file.name,
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, final_slug, entry))
    click.echo(f"added {final_slug} to library <- {parsed.url}")


def _add_monorepo(parsed: ParsedSource, slug: str | None, *,
                  expected_entry_file: str | None = None, refresh_existing_parent: bool = True) -> None:
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
    library_dir = library_agent_path(final_slug)  # validate slug before writes
    if Path(subpath).is_absolute() or ".." in Path(subpath).parts or "\\" in subpath:
        raise click.UsageError("agent subpath must be a safe repository-relative directory")
    lock_path = library_lock_path()
    lock = read_lock(lock_path)  # malformed locks must not advance shared backing
    existing_entry = lock.skills.get(final_slug)
    if existing_entry is not None:
        recorded = existing_entry.agent_path or f"{final_slug}.md"
        if (existing_entry.source != parsed.owner_repo or existing_entry.ref != parsed.ref
                or Path(recorded).parent != Path(subpath)
                or Path(recorded).name not in (f"{final_slug}.md", "AGENTS.md")
                or existing_entry.parent_url is None
                or skill_git.normalise_git_url(existing_entry.parent_url) != skill_git.normalise_git_url(parsed.url)):
            raise click.ClickException(f"{final_slug}: conflicting source/ref/path identity; refusing re-registration")

    parent_dir = agent_parent_clone_path(owner, repo, ref=parsed.ref, env=None)
    paths = registered_agent_paths(parent_dir, library=lock)
    if existing_entry is not None:
        paths[final_slug] = existing_entry.agent_path
    new_agent = None if existing_entry is not None else (final_slug, subpath)
    if not parent_dir.exists():
        try:
            _head, chosen = acquire_agent_parent(parent_dir,
                lambda stage: skill_git.clone_pinned_or_branch(parsed.url, stage, ref=parsed.ref, env=None),
                paths, new_agent=new_agent)
        except Exception as exc:
            raise click.ClickException(f"parent clone refused: {exc}") from exc
    else:
        if not skill_git.remote_matches(parent_dir, parsed.url, None):
            raise click.ClickException(f"{final_slug}: shared parent has a foreign origin: {parent_dir}")
        if skill_git.status(parent_dir, env=None) != skill_git.GitWorkingTreeStatus.CLEAN:
            raise click.ClickException(f"{final_slug}: dirty shared parent: {parent_dir}")
        # Never reset a shared checkout: a clean fast-forward is the only
        # permitted refresh. A divergent cache remains intact for inspection.
        if parsed.ref is not None and not skill_git._checked_out_at_ref(parent_dir, parsed.ref, None):
            raise click.ClickException(f"{final_slug}: shared parent ref conflict at {parent_dir}")
        from agent_toolkit_cli.skill_lock import looks_like_sha
        try:
            if looks_like_sha(parsed.ref) or not refresh_existing_parent:
                chosen = validate_agent_revision(parent_dir, skill_git.head_sha(parent_dir, env=None), paths, new_agent=new_agent)
            else:
                _head, chosen = refresh_agent_repo(parent_dir, source_url=parsed.url, ref=parsed.ref,
                                                  paths=paths, new_agent=new_agent)
        except (skill_git.GitError, RuntimeError) as exc:
            raise click.ClickException(f"{final_slug}: parent refresh refused: {exc}") from exc

    agent_root = parent_dir / subpath
    content_rel = existing_entry.agent_path if existing_entry is not None else chosen
    filename = Path(content_rel).name
    if expected_entry_file is not None and filename != expected_entry_file:
        raise click.ClickException(f"{final_slug}: source agent shape does not match catalog entryFile")
    if not (agent_root / filename).is_file():
        # Do NOT rmtree the shared parent on a missing content file.
        raise click.ClickException(
            f"{final_slug}: content file {content_rel} not found in parent "
            f"{parsed.owner_repo}; expected <subpath>/<slug>.md."
        )

    try:
        checked_agent_content(parent_dir, content_rel, final_slug)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if existing_entry is not None:
        click.echo(f"already in library: {final_slug}")
        return

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
