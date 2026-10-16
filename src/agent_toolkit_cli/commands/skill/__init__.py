"""`agent-toolkit-cli skill ...` subcommand group."""
from __future__ import annotations

import dataclasses
import os
import shutil
from pathlib import Path

import click
import yaml

from agent_toolkit_cli._group import AliasedGroup

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_agents import (
    AGENTS,
    detect_installed_agents,
)
from agent_toolkit_cli.paperclip_paths import (
    detect_paperclip_company,
    normalize_skill_project_root,
)
from agent_toolkit_cli.skill_install import (
    InstallError,
    InstallPlan,
    _current_linked_agents,
    _standard_bundle_link,
    apply as engine_apply,
    ensure_project_canonical,
    validate_projection_context,
)
from agent_toolkit_cli.skill_lock import (
    LockFile,
    looks_like_sha,
    read_lock,
    remove_entry,
    write_lock,
)
from agent_toolkit_cli.skill_paths import (
    is_skill_projection_available,
    library_lock_path,
    library_skill_path,
    lock_file_path,
)
from agent_toolkit_cli.skill_source import (
    ParsedSource,
    SourceParseError,
    parse_source,
    sanitize_ref,
)

from .doctor_cmd import doctor_cmd
from .import_cmd import import_cmd
from .list_cmd import list_cmd
from .push_cmd import push_cmd
from .reset_cmd import reset_cmd
from .status_cmd import status_cmd
from .update_cmd import update_cmd


def reconstruct_skill_into_library(
    parsed: ParsedSource,
    slug: str,
    *,
    pin_sha: str | None,
) -> tuple[str | None, str | None]:
    """Clone `parsed` into the library at `slug`; return (upstream_sha, local_sha).

    Single-repo: clone at parsed.ref, optionally checkout pin_sha, record SHAs.
    Monorepo: parent clone + subpath symlink, pinned when pin_sha is supplied.
    Does not touch the lock file — the caller owns lock mutation.
    """
    if parsed.subpath or parsed.skill_name:
        return _reconstruct_monorepo(parsed, slug, pin_sha=pin_sha)
    return _reconstruct_single(parsed, slug, pin_sha=pin_sha)


def _reconstruct_single(
    parsed: ParsedSource, slug: str, *, pin_sha: str | None,
) -> tuple[str | None, str | None]:
    library_dir = library_skill_path(slug)
    ref_is_full_sha = (
        parsed.ref is not None
        and len(parsed.ref) == 40
        and looks_like_sha(parsed.ref)
    )
    if not library_dir.exists():
        library_dir.parent.mkdir(parents=True, exist_ok=True)
        # Shallow clone — import only ever needs one commit's tree, never the
        # full history (#259). A fat monorepo source (pinchtab: 32 MB) would
        # otherwise dominate the whole run. `depth=1` no-ops to a full clone
        # for plain-local-path sources (git ignores --depth there) — harmless,
        # since real sources are https://github.com/... remotes.
        # `git clone --branch` cannot accept a SHA, so clone the default ref
        # before fetching and checking out that exact commit below.
        skill_git.clone(
            parsed.url,
            library_dir,
            ref=None if ref_is_full_sha else parsed.ref,
            env=None,
            depth=1,
        )
    effective_pin = pin_sha or (parsed.ref if ref_is_full_sha else None)
    if effective_pin and skill_git.is_git_repo(library_dir):
        # The depth-1 clone only holds branch HEAD's tree, so the pinned
        # (possibly older) commit must be fetched before it can be checked
        # out. fetch_ref of a SHA git already has is a cheap no-op.
        skill_git.fetch_ref(library_dir, ref=effective_pin, env=None, depth=1)
        skill_git.checkout(library_dir, ref=effective_pin, env=None)
    if skill_git.is_git_repo(library_dir):
        local_sha = skill_git.head_sha(library_dir, env=None)
        upstream_sha = (
            local_sha if ref_is_full_sha else skill_git.remote_head_sha(
                library_dir,
                ref=skill_git.resolve_ref(parsed.ref, library_dir),
                env=None,
            )
        )
    else:
        upstream_sha = None
        local_sha = None
    return upstream_sha, local_sha


def _reconstruct_monorepo(
    parsed: ParsedSource, slug: str, *, pin_sha: str | None,
) -> tuple[str | None, str | None]:
    from agent_toolkit_cli.skill_install import _symlink_or_copy
    from agent_toolkit_cli.skill_paths import parent_clone_path

    if parsed.owner_repo is None:
        raise click.ClickException("monorepo source must resolve to owner/repo")
    owner, repo = parsed.owner_repo.split("/", 1)
    parent_dir = parent_clone_path(owner, repo, ref=parsed.ref, env=None)
    if not parent_dir.exists():
        parent_dir.parent.mkdir(parents=True, exist_ok=True)
        # `git clone --branch` accepts branches/tags, not commit SHAs. Clone
        # SHA-ref imports at the remote default, then fetch and check out the
        # effective pin just as we do for a recorded older pin.
        ref_is_full_sha = (
            parsed.ref is not None
            and len(parsed.ref) == 40
            and looks_like_sha(parsed.ref)
        )
        clone_ref = None if ref_is_full_sha else parsed.ref
        skill_git.clone(
            parsed.url, parent_dir, ref=clone_ref, env=None, depth=1,
        )
        effective_pin = pin_sha or (parsed.ref if ref_is_full_sha else None)
        if effective_pin:
            skill_git.fetch_ref(parent_dir, ref=effective_pin, env=None, depth=1)
            skill_git.checkout(parent_dir, ref=effective_pin, env=None)
    else:
        if not skill_git.is_git_repo(parent_dir):
            raise click.ClickException(
                f"parent cache is not a git repository: {parent_dir}"
            )
        if (
            skill_git.status(parent_dir, env=None)
            is skill_git.GitWorkingTreeStatus.DIRTY
        ):
            raise click.ClickException(
                f"parent cache is dirty; refusing to move it: {parent_dir}"
            )
        existing_parent_sha = skill_git.head_sha(parent_dir, env=None)
        if pin_sha:
            # One shared parent working tree cannot represent two pins. Never
            # move it for an import: doing so changes already-imported siblings.
            if not existing_parent_sha.startswith(pin_sha):
                raise click.ClickException(
                    f"parent cache is at {existing_parent_sha}, not requested pin {pin_sha}; "
                    f"refusing to move shared parent {parent_dir}"
                )
        else:
            # --latest / add flow retains the existing ref-head refresh.
            ref = skill_git.resolve_ref(parsed.ref, parent_dir)
            try:
                skill_git.fetch_ref(parent_dir, ref=ref, env=None)
                skill_git.reset_hard(parent_dir, ref=ref, env=None)
            except Exception:
                pass
    if parsed.subpath:
        subpath = parsed.subpath
    else:
        assert parsed.skill_name is not None
        subpath = _resolve_skill_name_to_subpath(
            parent_dir, parsed.skill_name, source=parsed.owner_repo,
        )
    skill_root = parent_dir / subpath
    if not (skill_root / "SKILL.md").exists():
        raise click.ClickException(
            f"{subpath}/SKILL.md not found in parent {parsed.owner_repo}"
        )
    library_dir = library_skill_path(slug)
    if not library_dir.exists() and not library_dir.is_symlink():
        _symlink_or_copy(skill_root, library_dir)
    parent_sha = (
        skill_git.head_sha(parent_dir, env=None)
        if skill_git.is_git_repo(parent_dir) else None
    )
    return parent_sha, None


_SKILL_GROUP_EPILOG = """\
Examples:

\b
  # Add a skill to the global library (clone only — no symlinks yet)
  $ agent-toolkit-cli skill add anthropics/skills

\b
  # Pin to a branch or tag
  $ agent-toolkit-cli skill add anthropics/skills --ref main
  $ agent-toolkit-cli skill add anthropics/skills --ref v1.2.0

\b
  # Override the local slug
  $ agent-toolkit-cli skill add ajanderson1/journal-skill --slug journal

\b
  # Make it visible to a specific agent (claude-code) or all standard harnesses
  $ agent-toolkit-cli skill install journal --agents claude-code
  $ agent-toolkit-cli skill install journal --agents standard
  $ agent-toolkit-cli skill install journal --agents all

\b
  # Project install (canonical lives in the external project store)
  $ agent-toolkit-cli skill install journal --agents claude-code -p

\b
  # List, status, update, push
  $ agent-toolkit-cli skill list                  # global unless a project lock exists
  $ agent-toolkit-cli skill list -p               # project scope
  $ agent-toolkit-cli skill status                # clean / dirty / missing per skill
  $ agent-toolkit-cli skill update                # fetch + merge upstream for all
  $ agent-toolkit-cli skill update journal        # one skill only
  $ agent-toolkit-cli skill push journal          # self-improvements upstream

\b
  # Take down agent visibility but keep the canonical clone
  $ agent-toolkit-cli skill uninstall journal --agents claude-code

\b
  # Remove a skill completely (interactive picker if no slug given)
  $ agent-toolkit-cli skill remove journal
  $ agent-toolkit-cli skill remove                # interactive
  $ agent-toolkit-cli skill remove journal --force  # discard dirty changes
"""


@click.group(cls=AliasedGroup, epilog=_SKILL_GROUP_EPILOG)
def skill() -> None:
    """Manage skills via per-skill upstream git repos + skills-lock.json."""


def _resolve_agents(
    agents_str: str, scope: str, *, project: Path | None = None,
) -> tuple[str, ...]:
    """Expand a comma-separated --agents string into a tuple of agent names.

    Special values:
      "standard" → the standard bundle token (creates ~/.agents/skills/<slug>)
      "all"      → every agent detected as installed at the given scope, plus
                   Paperclip when the scope/project make it available (a
                   detected company project). Paperclip is never added by the
                   context-free catalog detector, so global `all` never selects
                   it merely because ~/.paperclip exists.

    Old spellings (universal, general-*) are no longer recognised (#356) and
    fall through to the unknown-token guard below.
    """
    if agents_str == "all":
        resolved = list(detect_installed_agents())
        if is_skill_projection_available(
            "paperclip", scope=scope, project=project,
        ):
            resolved.append("paperclip")
        return tuple(dict.fromkeys(resolved))
    parts = [p.strip() for p in agents_str.split(",") if p.strip()]
    # "standard" is a valid token; other names must be in the catalog.
    unknown = [p for p in parts if p != "standard" and p not in AGENTS]
    if unknown:
        raise click.UsageError(f"unknown agent(s): {', '.join(unknown)}")
    synthetic = [p for p in parts if p == "standard-skill"]
    if synthetic:
        raise click.UsageError(
            f"standard-skill is a synthetic catalog entry, not a usable agent token: "
            f"{', '.join(synthetic)}"
        )
    return tuple(parts)


@skill.command("add", epilog="""\
Examples:

\b
  agent-toolkit-cli skill add anthropics/skills
  agent-toolkit-cli skill add anthropics/skills --ref v1.2.0
  agent-toolkit-cli skill add ajanderson1/journal-skill --slug journal
""")
@click.argument("source", required=False)
@click.option("--source", "source_option", default=None,
              help="Add every skill from an exact owner/repo source.")
@click.option("--slug", default=None,
              help="Override the local slug.")
@click.option("--ref", default=None, help="Branch or tag to clone.")
@click.option("--skill", "skill_name_flag", default=None,
              help="Pick one skill from a monorepo by SKILL.md `name:`.")
@click.option("--owned", is_flag=True,
              help="Treat the monorepo parent as owned (writable). Implied "
                   "for known owned owners; this forces it for any parent.")
@click.pass_context
def add(
    ctx: click.Context, source: str | None, source_option: str | None,
    slug: str | None, ref: str | None, skill_name_flag: str | None, owned: bool,
) -> None:
    """Add SOURCE to the library, or batch-add with --source owner/repo."""
    if bool(source) == bool(source_option):
        raise click.UsageError("provide SOURCE or --source, but not both")
    if source_option is not None:
        _add_source_batch(source_option, ref, owned=owned)
        return
    assert source is not None
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise click.UsageError(str(exc)) from exc

    if ref is not None:
        try:
            ref = sanitize_ref(ref)
        except SourceParseError as exc:
            raise click.UsageError(str(exc)) from exc
        parsed = dataclasses.replace(parsed, ref=ref)

    if skill_name_flag is not None:
        if parsed.subpath is not None:
            raise click.UsageError(
                "--skill is ambiguous when SOURCE already names a subpath; "
                "pick one form."
            )
        if parsed.skill_name and parsed.skill_name != skill_name_flag:
            raise click.UsageError(
                f"--skill {skill_name_flag} conflicts with SOURCE's skill "
                f"({parsed.skill_name}); pick one form."
            )
        parsed = dataclasses.replace(parsed, skill_name=skill_name_flag)

    if parsed.subpath or parsed.skill_name:
        _add_monorepo(parsed, slug, owned=owned)
    else:
        from agent_toolkit_cli.skill_collection_register import register
        if parsed.owner_repo is not None and register(parsed, slug, owned=owned):
            return
        if owned:
            raise click.UsageError(
                "--owned only applies to a monorepo add (use --skill, a "
                "subpath, or owner/repo/<path>); a single-skill repo is "
                "pushed via its own remote."
            )
        _add_single(parsed, slug)


def _add_source_batch(source: str, ref: str | None, *, owned: bool) -> None:
    """Register every skill directory from an exact owner/repo source."""
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise click.UsageError(str(exc)) from exc
    if parsed.owner_repo != source or parsed.subpath or parsed.skill_name:
        raise click.UsageError("--source must be an exact owner/repo")
    if ref is not None:
        try:
            parsed = dataclasses.replace(parsed, ref=sanitize_ref(ref))
        except SourceParseError as exc:
            raise click.UsageError(str(exc)) from exc

    from agent_toolkit_cli.skill_collection_register import register
    if not register(parsed, None, owned=owned):
        if owned:
            raise click.UsageError("--owned only applies to a monorepo child")
        _add_single(parsed, None)


def _add_single(parsed: ParsedSource, slug: str | None) -> None:
    if slug is None:
        if parsed.owner_repo:
            slug = parsed.owner_repo.split("/", 1)[1]
            if slug.endswith("-skill"):
                slug = slug[:-6]
        else:
            slug = Path(parsed.url).name

    library_dir = library_skill_path(slug)
    lock_path = library_lock_path()

    from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock
    lock = read_lock(lock_path)
    existing_entry = lock.skills.get(slug)

    if existing_entry is not None:
        requested = parsed.owner_repo or parsed.url
        if existing_entry.source != requested or existing_entry.ref != parsed.ref:
            raise click.ClickException(
                f"{slug}: library entry exists with source {existing_entry.source!r} ref={existing_entry.ref!r}; "
                f"refusing to overwrite with {requested!r}. "
                f"Run `skill remove {slug}` first."
            )

    if not library_dir.exists():
        library_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone_pinned_or_branch(
                parsed.url, library_dir, ref=parsed.ref, env=None,
            )
        except Exception as exc:
            raise click.ClickException(f"clone failed: {exc}") from exc

    if skill_git.is_git_repo(library_dir):
        upstream_sha = skill_git.remote_head_sha(
            library_dir,
            ref=skill_git.resolve_ref(parsed.ref, library_dir),
            env=None,
        )
        local_sha = skill_git.head_sha(library_dir, env=None)
    else:
        upstream_sha = None
        local_sha = None

    entry = LockEntry(
        source=parsed.owner_repo or parsed.url,
        source_type=parsed.type,
        ref=parsed.ref,
        skill_path="SKILL.md",
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))
    click.echo(f"added {slug} to library <- {parsed.url}")


def _add_monorepo(parsed: ParsedSource, slug: str | None, *, owned: bool = False) -> None:
    """Register one child without moving a shared backing checkout."""
    from agent_toolkit_cli.skill_collection_register import register
    register(parsed, slug, owned=owned, single=True)


def _resolve_skill_name_to_subpath(
    parent_dir: Path, skill_name: str, source: str | None = None,
) -> str:
    """Walk parent_dir for SKILL.md files; pick the one whose frontmatter name matches.

    Raises ClickException with available names if none match. When more than one
    SKILL.md shares the requested name, the error hands the user a concrete way
    out: an explicit-subpath `skill add` command per match (using `source` as the
    owner/repo when known, else naming the bare subpaths).
    """
    candidates = []
    matches = []
    for skill_md in parent_dir.rglob("SKILL.md"):
        try:
            text = skill_md.read_text()
        except OSError:
            continue
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---", 4)
        if end == -1:
            continue
        try:
            fm = yaml.safe_load(text[4:end])
        except yaml.YAMLError:
            continue
        if not isinstance(fm, dict):
            continue
        name = fm.get("name")
        if name is None:
            continue
        rel = skill_md.parent.relative_to(parent_dir)
        candidates.append(str(name))
        if name == skill_name:
            matches.append(rel)
    if not matches:
        listing = ", ".join(sorted(candidates)) or "(none found)"
        raise click.ClickException(
            f"skill {skill_name!r} not found in parent. "
            f"Available: {listing}"
        )
    if len(matches) > 1:
        subpaths = [str(m) for m in matches]
        if source:
            hints = "\n".join(
                f"  skill add {source}/{sub}" for sub in subpaths
            )
        else:
            hints = "\n".join(
                f"  skill add <source>/{sub}  (or --skill {skill_name} "
                f"on a source already naming {sub})"
                for sub in subpaths
            )
        raise click.ClickException(
            f"skill {skill_name!r} matches multiple SKILL.md files: "
            f"{', '.join(subpaths)}.\n"
            f"The skills.sh URL form (/owner/repo/<name>) and a bare name "
            f"cannot disambiguate when two skills share a frontmatter name.\n"
            f"Address one by its explicit subpath instead:\n{hints}\n"
            f"  (shorthand: <owner>/<repo>/<subpath>; or tree URL: "
            f"https://github.com/<owner>/<repo>/tree/<ref>/<subpath>)"
        )
    return str(matches[0])


@skill.command("install", epilog="""\
Examples:

\b
  agent-toolkit-cli skill install journal --agents claude-code
  agent-toolkit-cli skill install journal --agents standard
  agent-toolkit-cli skill install journal --agents claude-code -p
""")
@click.argument("slug", required=False)
@click.option("--source", "source_filter", default=None,
              help="Install skills recorded from exact owner/repo.")
@click.option("--agents", "agents_str", default="standard", show_default=True,
              help="Comma-separated agent names, 'standard', or 'all'. "
                   "Defaults to the standard bundle.")
@click.option("--scope", "scope", default=None,
              type=click.Choice(["global", "project"]),
              help="Scope (default: global, or project inside a Paperclip "
                   "company).")
@click.option("-p", "--project", "project_flag", is_flag=True,
              help="Shorthand for --scope project.")
@click.pass_context
def install_cmd(
    ctx: click.Context, slug: str | None, source_filter: str | None,
    agents_str: str, scope: str | None, project_flag: bool,
) -> None:
    """Create agent-visibility symlinks for one skill or a source family.

    The skill must already be in the library (run `skill add` first).
    For --scope project, the project canonical is cloned from the global
    library's recorded source if not already present.
    """
    if bool(slug) == bool(source_filter):
        raise click.UsageError("provide SLUG or --source, but not both")
    candidate = (
        (ctx.obj.get("project_root") if ctx.obj else None) or Path.cwd()
    )
    context = detect_paperclip_company(candidate)
    if project_flag:
        scope = "project"
    elif scope is None:
        scope = "project" if context is not None else "global"
    project_root = (
        normalize_skill_project_root(candidate) if scope == "project" else None
    )

    try:
        target_agents = _resolve_agents(agents_str, scope, project=project_root)
    except click.UsageError:
        raise

    if not target_agents:
        click.echo(f"{slug or source_filter}: no agents specified; nothing to do")
        return
    if source_filter is not None:
        from agent_toolkit_cli.skill_lock import read_lock
        from agent_toolkit_cli.skill_collections import catalog
        from agent_toolkit_cli.skill_install import apply_collection_selection as apply_selection
        handled = set()
        try:
            for group in catalog(scope=scope, home=Path.home(), project=project_root):
                if group.source != source_filter:
                    continue
                apply_selection(group, {a: set(group.children) for a in target_agents},
                                scope=scope, home=Path.home(), project=project_root)
                handled.update(group.children)
                handled.add(group.wrapper)
                click.echo(f"installed collection {group.label}")
        except (InstallError, OSError) as exc:
            raise click.ClickException(str(exc)) from exc
        batch_lock = read_lock(library_lock_path())
        batch_slugs = sorted(
            name for name, entry in batch_lock.skills.items()
            if entry.source == source_filter and name not in handled
        )
        if not batch_slugs and not handled:
            click.echo(f"{source_filter}: no skills found in {scope} scope")
        for batch_slug in batch_slugs:
            ctx.invoke(
                install_cmd, slug=batch_slug, source_filter=None,
                agents_str=agents_str, scope=scope, project_flag=False,
            )
        return
    assert slug is not None

    if not target_agents:
        click.echo(f"{slug}: no agents specified; nothing to do")
        return

    try:
        validate_projection_context(
            slug=slug,
            target_agents=target_agents,
            scope=scope,
            home=None if scope == "project" else Path.home(),
            project=project_root,
        )
    except InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    from agent_toolkit_cli.skill_collections import catalog, exposed
    from agent_toolkit_cli.skill_install import apply_collection_selection as apply_selection
    try:
        for group in catalog(scope=scope, home=Path.home(), project=project_root):
            if slug not in group.children and slug != group.wrapper:
                continue
            selections = {}
            for agent in target_agents:
                selected = {n for n, c in group.children.items() if exposed(
                    c, group, agent, scope=scope, home=Path.home(), project=project_root)}
                selected.update(group.children if slug == group.wrapper else (slug,))
                selections[agent] = selected
            apply_selection(group, selections, scope=scope, home=Path.home(), project=project_root)
            click.echo(f"installed {slug} for {agents_str}")
            return
    except (InstallError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    global_lock_path = library_lock_path()

    if scope == "global":
        # Library canonical must already exist.
        library_dir = library_skill_path(slug)
        if not library_dir.exists():
            raise click.ClickException(
                f"{slug}: not in library. Run `skill add <source>` first."
            )
        # Build the plan using the library canonical as the source of truth.
        # We don't clone again — just create symlinks.
        p = InstallPlan(
            slug=slug, scope="global",
            source=None, ref=None,
            add_agents=target_agents, remove_agents=(),
        )
        try:
            result = engine_apply(p, home=None, project=None, env=None)
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        created = result.created
        skipped = result.skipped

    else:
        # Project scope: canonical is at <project>/.agents/skills/<slug>/.
        # project_root was normalized above (Paperclip descendants fold to the
        # company root); reuse it so the lock and canonical land there.
        assert project_root is not None
        try:
            ensure_project_canonical(
                slug=slug,
                project=project_root,
                global_lock_path=global_lock_path,
                env=None,
            )
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        except Exception as exc:
            raise click.ClickException(
                f"clone for project scope failed: {exc}"
            ) from exc

        # Under the external-store model every agent — including the synthetic
        # "standard" bundle token — projects via a symlink into the project
        # tree; apply() creates <project>/.agents/skills/<slug> for "standard".
        p = InstallPlan(
            slug=slug, scope="project",
            source=None, ref=None,
            add_agents=target_agents, remove_agents=(),
        )
        try:
            result = engine_apply(p, home=None, project=project_root, env=None)
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        created = result.created
        skipped = result.skipped

    if created:
        for link in created:
            click.echo(f"  linked {link}")
    if skipped:
        click.echo(f"  skipped (skip rule): {', '.join(skipped)}")
    click.echo(f"installed {slug} for {agents_str}")


@skill.command("uninstall", epilog="""\
Examples:

\b
  agent-toolkit-cli skill uninstall journal --agents claude-code
  agent-toolkit-cli skill uninstall journal --agents all
""")
@click.argument("slug", required=False)
@click.option("--source", "source_filter", default=None,
              help="Uninstall skills recorded from exact owner/repo.")
@click.option("--agents", "agents_str", default=None,
              help="Comma-separated agent names, 'standard', or 'all'. "
                   "Default (omitted): remove everywhere — the standard bundle "
                   "plus every detected agent.")
@click.option("--scope", "scope", default=None,
              type=click.Choice(["global", "project"]),
              help="Scope (default: global, or project inside a Paperclip "
                   "company).")
@click.option("-p", "--project", "project_flag", is_flag=True,
              help="Shorthand for --scope project.")
@click.pass_context
def uninstall_cmd(
    ctx: click.Context, slug: str | None, source_filter: str | None,
    agents_str: str | None, scope: str | None, project_flag: bool,
) -> None:
    """Remove visibility symlinks for one skill or a source family."""
    if bool(slug) == bool(source_filter):
        raise click.UsageError("provide SLUG or --source, but not both")
    candidate = (
        (ctx.obj.get("project_root") if ctx.obj else None) or Path.cwd()
    )
    context = detect_paperclip_company(candidate)
    if project_flag:
        scope = "project"
    elif scope is None:
        scope = "project" if context is not None else "global"
    project_root = (
        normalize_skill_project_root(candidate) if scope == "project" else None
    )

    if source_filter is not None:
        batch_lock_path = library_lock_path()
        batch_lock = read_lock(batch_lock_path)
        batch_slugs = sorted(
            name for name, entry in batch_lock.skills.items()
            if entry.source == source_filter
        )
        if not batch_slugs:
            click.echo(f"{source_filter}: no skills found in {scope} scope")
            return
        for batch_slug in batch_slugs:
            ctx.invoke(
                uninstall_cmd, slug=batch_slug, source_filter=None,
                agents_str=agents_str, scope=scope, project_flag=False,
            )
        return
    assert slug is not None

    if agents_str is None:
        # Maximal default — deliberately asymmetric with install's `standard`.
        # A bare uninstall must clean up EVERYWHERE the skill was projected, so we
        # union the synthetic `standard` token (the only thing that removes the
        # ~/.agents/skills/<slug> bundle symlink; `--agents all` excludes it
        # because the standard AgentConfig has detect_installed=False) with every
        # detected agent. Mirrors `agent uninstall`'s maximal resolver
        # (commands/agent/uninstall_cmd.py:_resolve_harnesses_for_uninstall, which
        # returns ("standard", *sorted(detected))). Computed here as a tuple rather
        # than via a token because _resolve_agents("standard,all") would raise.
        target_agents = ("standard", *detect_installed_agents())
        # Include Paperclip only inside a detected company project.
        if is_skill_projection_available(
            "paperclip", scope=scope, project=project_root,
        ):
            target_agents = (*target_agents, "paperclip")
    else:
        try:
            target_agents = _resolve_agents(
                agents_str, scope, project=project_root,
            )
        except click.UsageError:
            raise

    if not target_agents:
        click.echo(f"{slug}: no agents specified; nothing to do")
        return

    if scope == "global":
        p = InstallPlan(
            slug=slug, scope="global",
            source=None, ref=None,
            add_agents=(), remove_agents=target_agents,
        )
        try:
            result = engine_apply(p, home=None, project=None, env=None)
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        removed = result.removed
    else:
        # project_root was normalized above (Paperclip descendants fold to the
        # company root); reuse it so lock lookup matches the install target.
        assert project_root is not None
        # Every agent — including the synthetic "standard" bundle token —
        # projects via a symlink under the external-store model; apply() removes
        # <project>/.agents/skills/<slug> for "standard".
        p = InstallPlan(
            slug=slug, scope="project",
            source=None, ref=None,
            add_agents=(), remove_agents=target_agents,
        )
        try:
            result = engine_apply(p, home=None, project=project_root, env=None)
        except InstallError as exc:
            raise click.ClickException(str(exc)) from exc
        removed = result.removed

        # Project scope is non-destructive: the external canonical in the
        # per-project store is preserved (dirty work survives; doctor's orphan
        # sweep reclaims it later). Drop only the project lock entry.
        proj_lock_path = lock_file_path(scope="project", project=project_root)
        proj_lock = read_lock(proj_lock_path)
        if slug in proj_lock.skills:
            write_lock(proj_lock_path, remove_entry(proj_lock, slug))

    if removed:
        for link in removed:
            click.echo(f"  unlinked {link}")
    click.echo(f"uninstalled {slug} for {agents_str}")


@skill.command("remove", epilog="""\
Examples:

\b
  agent-toolkit-cli skill remove journal
  agent-toolkit-cli skill remove                    # interactive picker
  agent-toolkit-cli skill remove journal --force    # discard dirty changes
""")
@click.argument("slugs", nargs=-1, required=False)
@click.option("--source", "source_filter", default=None,
              help="Remove library skills recorded from exact owner/repo.")
@click.option("--force", is_flag=True, help="Remove even if working tree is dirty.")
@click.pass_context
def remove_cmd(
    ctx: click.Context, slugs: tuple[str, ...], source_filter: str | None,
    force: bool,
) -> None:
    """Remove selected skills from the library."""
    if source_filter is not None and slugs:
        raise click.UsageError("provide slugs or --source, but not both")
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    if source_filter is not None:
        slugs = tuple(sorted(
            name for name, entry in lock.skills.items()
            if entry.source == source_filter
        ))
        if not slugs:
            click.echo(f"{source_filter}: no skills found in library")
            return

    if not slugs:
        from . import wizard as _wizard
        installed = tuple(sorted(lock.skills))
        descriptions = {s: f"in library: {library_skill_path(s)}"
                        for s in installed}
        picked = _wizard.select_slug_to_remove(
            installed_slugs=installed, slug_descriptions=descriptions,
        )
        slugs = picked.slugs
        if not slugs:
            click.echo("(nothing selected)")
            return

    had_dirty = False
    for slug in slugs:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in library")
            continue

        library_dir = library_skill_path(slug)
        effective_force = force

        if not force:
            from . import wizard as _wizard
            will_delete = [str(library_dir)]
            # Enumerate known symlinks.
            bundle_link = _standard_bundle_link(slug)
            if bundle_link.is_symlink():
                will_delete.append(str(bundle_link))
            for name in AGENTS:
                if name == "standard":
                    continue
                try:
                    from agent_toolkit_cli.skill_paths import agent_projection_dir
                    link = agent_projection_dir(
                        name, slug, scope="global", home=None, project=None,
                    )
                    if link.is_symlink():
                        will_delete.append(str(link))
                except Exception:
                    pass
            mode = _wizard.select_remove_mode(
                slug=slug, will_delete=tuple(will_delete),
            )
            if not mode.confirmed:
                click.echo(f"{slug}: skipped")
                continue
            if mode.mode == "unlink":
                # Remove all global symlinks but keep library dir + lock entry.
                _remove_all_global_symlinks(slug)
                click.echo(f"{slug}: unlinked (library kept)")
                continue
            effective_force = True

        if library_dir.exists() and skill_git.is_git_repo(library_dir) and not effective_force:
            wt = skill_git.status(library_dir, env=None)
            if wt == skill_git.GitWorkingTreeStatus.DIRTY:
                click.echo(f"{slug}: dirty — push or use --force to discard")
                had_dirty = True
                continue

        # Full remove: unlink all global symlinks + remove the library entry
        # (symlink → unlink + sweep orphan parent clone; directory → rmtree).
        _remove_all_global_symlinks(slug)
        parent_clone_to_check: Path | None = None
        if library_dir.is_symlink():
            target = Path(os.readlink(library_dir))
            if not target.is_absolute():
                target = (library_dir.parent / target).resolve(strict=False)
            parent_clone_to_check = _enclosing_parent_clone(target)
            library_dir.unlink()
        elif library_dir.exists():
            shutil.rmtree(library_dir)
        lock = remove_entry(lock, slug)
        write_lock(lock_path, lock)
        if parent_clone_to_check is not None and parent_clone_to_check.exists():
            _cleanup_parent_clone_if_orphaned(parent_clone_to_check, lock)
        click.echo(f"{slug}: removed")

    if had_dirty:
        ctx.exit(1)


def _remove_all_global_symlinks(slug: str) -> None:
    """Remove the standard bundle link and all non-standard agent links at global scope."""
    bundle_link = _standard_bundle_link(slug)
    if bundle_link.is_symlink():
        bundle_link.unlink()

    for name in AGENTS:
        if name == "standard":
            continue
        cfg = AGENTS[name]
        if cfg.is_standard:
            continue
        link = cfg.global_skills_dir / slug
        if link.is_symlink():
            link.unlink()


def _enclosing_parent_clone(target: Path) -> Path | None:
    """Return the `_parents/<owner>/<repo>[@<ref>]/` ancestor of `target`, or None.

    Monorepo library symlinks point into
    ``<library_root>/_parents/<owner>/<repo>[@<ref>]/<subpath>``. Climb the
    parents until we hit a directory whose own parent is named ``_parents`` —
    that is the per-(owner, repo, ref) clone we may need to sweep. Returns
    None if `target` is not under a `_parents/` tree (defensive — we won't
    sweep a directory we can't positively identify as a parent clone).
    """
    for ancestor in target.parents:
        if ancestor.parent.name == "_parents":
            return ancestor
    return None


def _cleanup_parent_clone_if_orphaned(
    parent_clone: Path, lock: LockFile,
) -> bool:
    """Remove `parent_clone` if no remaining lock entry's library symlink targets it.

    Walks current lock entries, resolves each canonical's symlink target, and
    checks whether `parent_clone` is an ancestor. If any sibling still points
    in, leave the clone intact (it is still shared). Otherwise rmtree it.
    Returns True iff the clone was removed.
    """
    for sibling_slug in lock.skills:
        sibling = library_skill_path(sibling_slug)
        if not sibling.is_symlink():
            continue
        sibling_target = Path(os.readlink(sibling))
        if not sibling_target.is_absolute():
            sibling_target = (sibling.parent / sibling_target).resolve(
                strict=False,
            )
        if parent_clone in sibling_target.parents:
            return False
    shutil.rmtree(parent_clone)
    return True


def _count_linked(slug: str, scope: str, home: Path | None, project: Path | None) -> str:
    linked = _current_linked_agents(
        slug=slug, scope=scope, home=home, project=project,
    )
    return ", ".join(linked[:3]) + ("..." if len(linked) > 3 else "")


skill.add_command(import_cmd)
skill.add_command(list_cmd)
skill.add_command(status_cmd)
skill.add_command(update_cmd)
skill.add_command(push_cmd)
skill.add_command(reset_cmd)
skill.add_command(doctor_cmd)

# Surface aliases to match `npx -y skills` muscle memory (#169).
skill.add_command(list_cmd, name="ls")
skill.add_command(remove_cmd, name="rm")
