"""`agent import <file>` — reconstruct the global library from a lock file.

Additive merge: only slugs absent locally are added (skip-if-exists). Per-slug
clone failures are non-fatal; exit code is 1 if any failed.

Lock is written ONLY after a successful clone (lock honesty, #283 class of bug).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path, PurePosixPath

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli._install_core import _symlink_or_copy
from agent_toolkit_cli.agent_lock import (
    LockEntry,
    add_entry,
    clone_url_from_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.skill_lock import looks_like_sha
from agent_toolkit_cli.skill_source import parse_source, sanitize_ref
from agent_toolkit_cli.agent_paths import (
    agent_parent_clone_path,
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


def _validated_agent_path(slug: str, value: str | None) -> PurePosixPath:
    """Return a safe portable content path ending in the canonical filename."""
    raw = value or f"{slug}.md"
    if "\\" in raw:
        raise ValueError(f"{slug}: invalid agentPath {raw!r}")
    parts = raw.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{slug}: invalid agentPath {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or path.name != f"{slug}.md":
        raise ValueError(
            f"{slug}: agentPath must end with {slug}.md, got {raw!r}"
        )
    return path


def _category_identity(
    entry: LockEntry, slug: str,
) -> tuple[str, str, str]:
    """Resolve a safe cache identity and authoritative clone transport."""
    source = entry.source[:-4] if entry.source.lower().endswith(".git") else entry.source
    parts = source.split("/")
    safe = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    if (
        entry.source_type not in {"github", "gitlab", "git"}
        or len(parts) < 2
        or not all(safe.fullmatch(part) and part not in {".", ".."} for part in parts)
    ):
        raise ValueError(
            f"{slug}: category agent source must be portable owner/repo shorthand"
        )
    owner_repo = "/".join(parts)
    if entry.parent_url:
        parsed = parse_source(entry.parent_url)
        if parsed.owner_repo != owner_repo or parsed.subpath is not None:
            raise ValueError(f"{slug}: parentUrl does not match source identity")
        source_url = parsed.url
    elif entry.source_type in {"github", "gitlab"}:
        source_url = clone_url_from_entry(entry)
    else:
        raise ValueError(f"{slug}: generic category source requires parentUrl")
    return parts[0], "/".join(parts[1:]), source_url


def _clone_at_requested_revision(
    source_url: str,
    destination: Path,
    *,
    ref: str | None,
    pin: str | None,
) -> str:
    """Clone one repository and return its exact landed commit."""
    ref_is_sha = looks_like_sha(ref)
    skill_git.clone(
        source_url, destination, ref=None if ref_is_sha else ref,
        env=None, depth=1,
    )
    effective_pin = pin or (ref if ref_is_sha else None)
    if effective_pin:
        skill_git.fetch_ref(destination, ref=effective_pin, env=None, depth=1)
        skill_git.checkout(destination, ref=effective_pin, env=None)
    return skill_git.head_sha(destination, env=None)


def _assert_safe_parent(
    parent: Path,
    *,
    source_url: str,
    expected_head: str | None,
    ref: str | None,
    slug: str,
) -> str:
    """Fail closed before reusing a shared parent clone."""
    if not skill_git.is_git_repo(parent):
        raise ValueError(f"{slug}: shared parent is not a Git checkout")
    if skill_git.status(parent, env=None) is not skill_git.GitWorkingTreeStatus.CLEAN:
        raise ValueError(f"{slug}: shared parent is dirty")
    if not skill_git.remote_matches(parent, source_url, env=None):
        raise ValueError(f"{slug}: shared parent source does not match lock")
    head = skill_git.head_sha(parent, env=None)
    if expected_head:
        if head != expected_head:
            raise ValueError(
                f"{slug}: shared parent is at {head}, expected {expected_head}"
            )
        return head
    if ref is None:
        resolved_ref, remote_head = skill_git.live_remote_default_head(
            parent, env=None,
        )
    else:
        resolved_ref = ref
        remote_head = skill_git.live_remote_head_sha(
            parent, ref=resolved_ref, env=None,
        )
    branch = skill_git.current_branch(parent, env=None)
    if branch != resolved_ref:
        raise ValueError(
            f"{slug}: shared parent is on {branch}, expected {resolved_ref}"
        )
    if head != remote_head:
        raise ValueError(
            f"{slug}: shared parent is stale at {head}, latest is {remote_head}"
        )
    return head


def _assert_category_content(
    parent: Path, agent_path: PurePosixPath, slug: str,
) -> Path:
    """Validate the category content path without following foreign symlinks."""
    current = parent
    for component in agent_path.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(f"{slug}: agentPath contains a symlink")
    content = parent.joinpath(*agent_path.parts)
    if not content.is_file():
        raise ValueError(f"{slug}: canonical content file missing: {agent_path}")
    try:
        content.resolve(strict=True).relative_to(parent.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{slug}: agentPath escapes shared parent") from exc
    return content.parent


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
        if canonical.exists() or canonical.is_symlink():
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (store copy already exists)")
            continue

        source_url = clone_url_from_entry(entry)
        ref = entry.ref
        pin_sha = None if latest else entry.upstream_sha
        effective_pin = pin_sha or (ref if looks_like_sha(ref) else None)
        created_path: Path | None = None
        created_parent: Path | None = None

        try:
            if ref is not None:
                ref = sanitize_ref(ref)
            agent_path = _validated_agent_path(slug, entry.agent_path)
            canonical.parent.mkdir(parents=True, exist_ok=True)
            if agent_path.parent == PurePosixPath("."):
                created_path = canonical
                local_sha = _clone_at_requested_revision(
                    source_url, canonical, ref=ref, pin=pin_sha,
                )
                _assert_category_content(canonical, agent_path, slug)
                upstream_sha = effective_pin or local_sha
                new_entry = LockEntry(
                    source=entry.source,
                    source_type=entry.source_type,
                    ref=entry.ref,
                    agent_path=agent_path.as_posix(),
                    upstream_sha=upstream_sha,
                    local_sha=local_sha,
                    parent_url=entry.parent_url,
                    read_only=entry.read_only,
                )
            else:
                owner, repo, parent_source_url = _category_identity(entry, slug)
                parent = agent_parent_clone_path(owner, repo, ref=ref, env=None)
                if parent.exists() or parent.is_symlink():
                    landed = _assert_safe_parent(
                        parent, source_url=parent_source_url,
                        expected_head=effective_pin, ref=ref, slug=slug,
                    )
                else:
                    parent.parent.mkdir(parents=True, exist_ok=True)
                    created_parent = parent
                    landed = _clone_at_requested_revision(
                        parent_source_url, parent, ref=ref, pin=pin_sha,
                    )
                agent_root = _assert_category_content(parent, agent_path, slug)
                created_path = canonical
                materialised = _symlink_or_copy(agent_root, canonical)
                new_entry = LockEntry(
                    source=entry.source,
                    source_type=entry.source_type,
                    ref=entry.ref,
                    agent_path=agent_path.as_posix(),
                    upstream_sha=landed,
                    local_sha=None,
                    parent_url=entry.parent_url or parent_source_url,
                    read_only=entry.read_only,
                    extras={"materialised": "copy"} if materialised == "copy" else {},
                )
            next_current = add_entry(current, slug, new_entry)
            # Persist after EACH added agent. Keeping the write inside the
            # owned-path transaction lets failure cleanup preserve lock honesty.
            write_lock(library_lock_path(), next_current)

        except Exception as exc:  # noqa: BLE001 — report, don't abort
            failed.append((slug, str(exc)))
            click.echo(f"  failed   {slug}  ({exc})")
            # Lock honesty (#283): never retain a failed canonical or a parent
            # clone created solely for the failed entry.
            if created_path is not None:
                if created_path.is_symlink():
                    created_path.unlink(missing_ok=True)
                elif created_path.exists():
                    shutil.rmtree(created_path, ignore_errors=True)
            if created_parent is not None and created_parent.exists():
                shutil.rmtree(created_parent, ignore_errors=True)
            continue
        current = next_current
        landed = (new_entry.local_sha or new_entry.upstream_sha or "")[:7]
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
