"""Agent-flavoured facade over `_paths_core.py`.

v3.0.0 PR2 — mirrors `skill_paths.py` for the agent (subagent) asset type.

v3.0.0 model — library vs install:

  Global scope canonical lives in the library at
  ~/.agent-toolkit/agents/<slug>/. Entries may be standalone working trees
  or directory aliases into verified shared Git parents. Harnesses reach a library agent via a file/symlink/registry
  entry created by `agent install`. The global lock is at
  ~/.agent-toolkit/agents-lock.json.

  New project scope uses central library backing. Recorded private backing
  stays private in its separate agents store; old shared-skills paths remain
  readable. Project lock at <project>/agents-lock.json.

Public symbols (`canonical_agent_dir`, `lock_file_path`, `library_root`,
`library_agent_path`, `library_lock_path`, `project_id`,
`project_store_root`, `project_parents_root`, `parent_clone_path`,
`agent_projection_dir`, `harness_projection_dir`, `SUPPORTED_HARNESSES`,
`Scope`) are preserved verbatim — implementations delegate to
`_paths_core` where the binding-driven helpers live.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    AGENT_BINDING,
    library_lock_path_for_asset_type,
    library_root_for_asset_type,
)
# Shared helpers (independent of asset type) re-exported from skill_paths.
# Re-exporting (rather than hoisting into _paths_core) is deliberate: it
# avoids touching PR1's frozen public surface mid-cycle. Hoist to an asset-type-
# agnostic module once both facades have shipped and stabilised (PR3+).
from agent_toolkit_cli.skill_paths import (
    SUPPORTED_HARNESSES,
    agent_projection_dir,
    harness_projection_dir,
    parent_clone_path,
    project_id,
)

Scope = Literal["project", "global"]


# Machine-checked re-export contract. ruff/pyflakes treat __all__ membership
# as use, so the re-exports above stay even without internal callers.
__all__ = [
    "AGENT_BINDING",
    "Scope",
    "SUPPORTED_HARNESSES",
    "agent_parent_clone_path",
    "agent_projection_dir",
    "canonical_agent_dir",
    "harness_projection_dir",
    "library_agent_path",
    "library_lock_path",
    "library_root",
    "lock_file_path",
    "parent_clone_path",
    "project_id",
    "project_parents_root",
    "project_store_root",
]


def project_store_root(project: Path, *, env: dict[str, str] | None = None) -> Path:
    return library_root(env).parent / "projects" / project_id(project) / "agents"


def project_parents_root(project: Path) -> Path:
    return project_store_root(project)


def library_root(env: dict[str, str] | None = None) -> Path:
    """Return the root of the global agent library.

    Thin shim over `_paths_core.library_root_for_asset_type(AGENT_BINDING, …)`.
    Does NOT honor $AGENT_TOOLKIT_SKILLS_ROOT (that env var is skill-only).
    """
    return library_root_for_asset_type(AGENT_BINDING, env)


def library_agent_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    """Return the canonical library path for a single agent slug."""
    from agent_toolkit_cli._paths_core import validate_asset_slug
    validate_asset_slug(slug)
    return library_root(env) / slug


def agent_parent_clone_path(
    owner: str, repo: str, *, ref: str | None, env: dict[str, str] | None = None,
) -> Path:
    """Where a monorepo (category-repo) parent is cloned for AGENT slugs.

    The bare `parent_clone_path` re-exported above resolves its base from the
    SKILL library root (its default `root` is skill_paths.library_root). An
    agent monorepo parent must cache under the AGENT tree
    (`<agent_library_root>/_parents/<owner>/<repo>[@<ref>]/`) so it doesn't
    pollute the skills library and so agent doctor/remove find it where they
    look. Pass the agent `library_root` explicitly as `root`.
    """
    return parent_clone_path(owner, repo, ref=ref, root=library_root(env))


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    """Return the path of the global agents-lock.json."""
    return library_lock_path_for_asset_type(AGENT_BINDING, env)


def canonical_agent_dir(
    slug: str,
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Return the canonical on-disk path for an agent at the given scope.

    Global scope: delegates to library_agent_path(slug). `home` accepted
    for backward compatibility but ignored — library root is always
    determined by AGENT_BINDING.

    Project scope: <store_root>/<slug> (external store — shared with
    skills via the same project_store_root).
    """
    if scope == "global":
        return library_agent_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    from agent_toolkit_cli.project_backing import resolve
    return resolve(AGENT_BINDING, slug, project, home=home)


def lock_file_path(
    *,
    scope: Scope,
    home: Path | None = None,
    project: Path | None = None,
) -> Path:
    """Return the lock file path for the given scope.

    Global scope: delegates to library_lock_path(). `home` accepted for
    backward compatibility but ignored.

    Project scope: <project>/<AGENT_BINDING.lock_filename> — uses the
    binding so the per-project lock lands at <project>/agents-lock.json.
    """
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / AGENT_BINDING.lock_filename


def _agent_parts(relative: str, slug: str) -> list[str]:
    from agent_toolkit_cli._install_core import InstallError
    parts = relative.split("/")
    if (not relative or Path(relative).is_absolute() or "\\" in relative
            or any(p in ("", ".", "..") for p in parts)):
        raise InstallError(f"{slug}: invalid agentPath {relative!r}")
    return parts


def checked_agent_content(root: Path, relative: str, slug: str) -> Path:
    """Resolve a recorded entry without traversing source/content symlinks."""
    from agent_toolkit_cli._install_core import InstallError
    parts = _agent_parts(relative, slug)
    content = root
    for component in parts:
        content = content / component
        if content.is_symlink():
            raise InstallError(f"{slug}: agentPath contains a symlink: {content}")
    if not content.is_file() or not content.resolve().is_relative_to(root.resolve()):
        raise InstallError(f"{slug}: missing or escaping agentPath {relative!r}")
    return content


def agent_content_path(canonical: Path, slug: str, entry=None) -> Path:
    """Recorded content wins over incidental repository-maintenance AGENTS.md."""
    from agent_toolkit_cli._install_core import InstallError
    relative = (entry.agent_path or f"{slug}.md") if entry is not None else (
        f"{slug}.md" if (canonical / f"{slug}.md").is_file() else "AGENTS.md")
    # Validate the entire recorded path even when a private copy is rooted at
    # the selected entry directory rather than the original repository root.
    _agent_parts(relative, slug)
    filename = Path(relative).name
    if entry is not None and entry.parent_url and canonical.resolve() == library_agent_path(slug).resolve():
        from agent_toolkit_cli.skill_source import parse_source
        parsed = parse_source(entry.parent_url)
        if parsed.owner_repo is None or parsed.owner_repo.removesuffix(".git") != entry.source.removesuffix(".git"):
            raise InstallError(f"{slug}: parent URL/source identity mismatch")
        owner, repo = entry.source.split("/", 1)
        from agent_toolkit_cli.skill_paths import resolve_existing_parent_clone
        parent = resolve_existing_parent_clone(owner, repo, ref=entry.ref,
            parent_url=entry.parent_url, root=library_root())
        if not parent.exists() and repo.endswith(".git"):
            # Older tree-URL registrations kept .git in source/cache keys;
            # import normalizes the cache key while preserving the lock URL.
            parent = resolve_existing_parent_clone(owner, repo.removesuffix(".git"),
                ref=entry.ref, parent_url=entry.parent_url, root=library_root())
        from agent_toolkit_cli import skill_git
        if not skill_git.remote_matches(parent, entry.parent_url, None):
            raise InstallError(f"{slug}: foreign shared parent origin")
        content = checked_agent_content(parent, relative, slug)
        if canonical.resolve() != content.parent.resolve():
            raise InstallError(f"{slug}: foreign agent canonical target: {canonical}")
    else:
        content = checked_agent_content(canonical, filename, slug)
    return canonical if filename == "AGENTS.md" else content


def agent_git_root(canonical: Path, slug: str, entry, *, project=None) -> Path:
    """Resolve the selected checkout, never substitute the central library."""
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.project_backing import verify_gitfile_worktree
    _agent_parts(entry.agent_path or f"{slug}.md", slug)
    if skill_git.is_git_repo(canonical):
        root = canonical.resolve()
    elif entry.parent_url and canonical.is_symlink():
        agent_content_path(canonical, slug, entry)  # current containment/identity
        target = canonical.readlink()
        root = target if target.is_absolute() else canonical.parent / target
        for _ in Path(entry.agent_path).parent.parts:
            root = root.parent
        root = root.resolve()
        if not skill_git.is_git_repo(root):
            raise InstallError(f"{slug}: no owned Git checkout for this agent")
    else:
        raise InstallError(f"{slug}: no .git/ in selected backing; cannot refresh copy-mode agent")
    verify_gitfile_worktree(root)
    if project is not None and entry.extras.get("projectBacking") != "central":
        from agent_toolkit_cli.project_backing import private_candidates
        roots = [p.parent for p in private_candidates(AGENT_BINDING, slug, project)]
        if (canonical.resolve() == library_agent_path(slug).resolve()
                or (canonical.is_symlink() and skill_git.is_git_repo(canonical))
                or not any(not base.is_symlink() and not base.parent.is_symlink()
                           and root.is_relative_to(base.resolve()) for base in roots)):
            raise InstallError(f"{slug}: private backing does not own this project checkout; refusing mutation of central/another worktree")
    return root


def registered_agent_paths(repo: Path, *, library=None, scoped=None, project=None) -> dict[str, str]:
    """Paths whose existing projections share this exact working tree.

    Inspect symlink targets lexically: resolving an entry after an unsafe
    upstream replacement would hide which parent actually owns it.
    """
    import os
    from agent_toolkit_cli.agent_lock import read_lock
    library = library if library is not None else read_lock(library_lock_path())
    def relative_target(target):
        # Resolve prefixes, never the entry suffix: HOME/library prefixes may
        # themselves be symlinks, and an entry may already be substituted.
        target = Path(os.path.abspath(target))
        for prefix in (target, *target.parents):
            if prefix.resolve() == repo.resolve():
                return target.relative_to(prefix)
        return None

    paths = {}
    groups = [(library, None)] + ([(scoped, project)] if scoped is not None else [])
    for records, consumer in groups:
        for slug, entry in records.skills.items():
            canonical = library_agent_path(slug) if consumer is None else canonical_agent_dir(slug, scope="project", project=consumer)
            relative = entry.agent_path or f"{slug}.md"
            _agent_parts(relative, slug)
            if canonical.is_symlink():
                target = canonical.readlink()
                target = target if target.is_absolute() else canonical.parent / target
                suffix = relative_target(target)
                if suffix is not None:
                    if suffix != Path(relative).parent:
                        from agent_toolkit_cli._install_core import InstallError
                        raise InstallError(f"{slug}: shared backing/agentPath identity mismatch")
                    paths[slug] = relative
            if canonical.resolve() == repo.resolve():
                paths[slug] = Path(relative).name  # standalone/private root
    # A retained canonical alias may still serve an unlisted project. Without
    # its recorded selection we cannot safely advance this parent by guessing.
    if library_root().is_dir():
        for alias in library_root().iterdir():
            if alias.is_symlink() and alias.name not in library.skills and alias.name not in paths:
                target = alias.readlink()
                target = target if target.is_absolute() else alias.parent / target
                if relative_target(target) is not None:
                    from agent_toolkit_cli._install_core import InstallError
                    raise InstallError(f"{alias.name}: unrecorded agent alias shares this backing; restore registration before refresh")
    return paths


def validate_agent_revision(repo: Path, revision: str, paths: dict[str, str], *, new_agent=None) -> str | None:
    """Prove entry and payload containment in Git objects BEFORE checkout.

    No prospective file is opened through an active library projection.
    Supporting symlinks may remain inside the repository; escaping, dangling,
    cyclic links and unproven submodule resources are refused.
    """
    import posixpath
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli._install_core import InstallError
    raw = skill_git._run(["git", "-C", str(repo), "ls-tree", "-r", "-t", "-z", revision], env=None).stdout
    tree = {".": ("040000", revision)}
    for record in raw.split("\0"):
        if record:
            meta, name = record.split("\t", 1)
            mode, _kind, oid = meta.split()
            tree[name] = (mode, oid)
    selected = dict(paths)
    chosen = None
    if new_agent is not None:
        slug, directory = new_agent
        prefix = "" if directory in ("", ".") else directory.rstrip("/") + "/"
        flat = f"{prefix}{slug}.md"
        directory_entry = f"{prefix}AGENTS.md"
        chosen = flat if flat in tree or directory_entry not in tree else directory_entry
        selected[slug] = chosen

    checked_directories = set()

    def resource_target(name):
        def resolve_parts(parts, resolved, active):
            for part in parts:
                # POSIX traversal expands links BEFORE a following '..'. Also,
                # file/.. is ENOTDIR, not a lexical cancellation of the file.
                if tree["/".join(resolved) or "."][0] != "040000":
                    raise InstallError(f"unproven prospective agent resource: {name}")
                if part in ("", "."):
                    continue
                if part == "..":
                    if not resolved:
                        raise InstallError(f"escaping agent resource symlink: {name}")
                    resolved = resolved[:-1]
                    continue
                prefix = "/".join([*resolved, part])
                node = tree.get(prefix)
                if node is None:
                    raise InstallError(f"missing prospective agent resource: {name}")
                if node[0] == "120000":
                    if prefix in active:
                        raise InstallError(f"cyclic agent resource symlink: {name}")
                    target = skill_git._run(["git", "-C", str(repo), "cat-file", "blob", node[1]], env=None).stdout
                    if not target or posixpath.isabs(target) or "\\" in target or "\0" in target:
                        raise InstallError(f"escaping agent resource symlink: {name}")
                    resolved = resolve_parts(target.split("/"), resolved, active | {prefix})
                elif node[0] == "160000":
                    raise InstallError(f"unproven prospective agent resource: {name}")
                else:
                    resolved = [*resolved, part]
            return resolved

        directory = "/".join(resolve_parts(name.split("/"), [], set()))
        if tree[directory or "."][0] == "040000" and directory not in checked_directories:
            checked_directories.add(directory)
            # A directory alias exposes its descendants too, including those
            # outside the agent's lexical subtree but inside this repository.
            for child, (mode, _oid) in tree.items():
                if not directory or child.startswith(directory + "/"):
                    if mode == "120000":
                        resource_target(child)
                    elif mode == "160000":
                        raise InstallError(f"unproven submodule resource: {child}")

    for slug, relative in selected.items():
        parts = _agent_parts(relative, slug)
        for index in range(len(parts)):
            prefix = "/".join(parts[:index + 1])
            node = tree.get(prefix)
            if node is not None and node[0] == "120000":
                raise InstallError(f"{slug}: prospective agentPath contains a symlink: {prefix}")
            expected = ("100644", "100755") if index == len(parts) - 1 else ("040000",)
            if node is None or node[0] not in expected:
                raise InstallError(f"{slug}: canonical content file missing or unsupported: {relative} (prospective path {prefix})")
        if parts[-1] == "AGENTS.md":
            directory = posixpath.dirname(relative)
            for name, (mode, _oid) in tree.items():
                if not directory or name.startswith(directory + "/"):
                    if mode == "120000":
                        resource_target(name)
                    elif mode == "160000":
                        raise InstallError(f"{slug}: unproven submodule resource: {name}")
    return chosen


def refresh_agent_repo(repo: Path, *, source_url: str, ref, paths, reset=False, force=False, new_agent=None):
    """Fetch, validate the exact prospective commit, then move only this tree."""
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.project_backing import verify_gitfile_worktree
    verify_gitfile_worktree(repo)
    if not skill_git.remote_matches(repo, source_url, None):
        raise InstallError(f"{repo}: foreign origin; refusing agent refresh")
    actual = skill_git._run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"], env=None).stdout.strip()
    if Path(actual).resolve() != repo.resolve():
        raise InstallError(f"{repo}: Git working tree differs from selected backing; refusing mutation")
    try:
        branch = skill_git._run(["git", "-C", str(repo), "symbolic-ref", "--quiet", "HEAD"], env=None).stdout.strip()
    except skill_git.GitError as exc:
        if exc.returncode != 1:
            raise
        branch = None  # a detached worktree has its own HEAD
    if branch:
        worktrees = skill_git._run(["git", "-C", str(repo), "worktree", "list", "--porcelain", "-z"], env=None).stdout
        for record in worktrees.split("\0\0"):
            fields = record.split("\0")
            if f"branch {branch}" in fields:
                other = next(field.removeprefix("worktree ") for field in fields if field.startswith("worktree "))
                if Path(other).resolve() != repo.resolve():
                    raise InstallError(f"{repo}: branch also checked out in another worktree: {other}; refusing shared HEAD mutation")
    if not force and skill_git.status(repo, env=None) != skill_git.GitWorkingTreeStatus.CLEAN:
        raise InstallError(f"{repo}: dirty backing; refusing agent refresh")
    resolved = skill_git.resolve_ref(ref, repo)
    # Fetch objects/FETCH_HEAD without advancing any registered branch/tag or
    # remote-tracking ref before the prospective tree has passed validation.
    skill_git._run(["git", "-C", str(repo), "fetch", "--no-tags", "--refmap=", "origin", skill_git._guard_ref(resolved)], env=None)
    target = skill_git._run(["git", "-C", str(repo), "rev-parse", "FETCH_HEAD^{commit}"], env=None).stdout.strip()
    chosen = validate_agent_revision(repo, target, paths, new_agent=new_agent)
    # Do not pull/fetch again after validation: use this exact object ID.
    args = ["reset", "--hard", target] if reset else ["merge", "--ff-only", "--no-edit", target]
    skill_git._run(["git", "-C", str(repo), *args], env=None)
    # Update an existing native tracking ref only AFTER acceptance, so normal
    # Git status/provenance remain accurate without changing refs on refusal.
    tracking = f"refs/remotes/origin/{resolved.removeprefix('refs/heads/')}"
    try:
        skill_git._run(["git", "-C", str(repo), "show-ref", "--verify", "--quiet", tracking], env=None)
    except skill_git.GitError:
        pass  # tags/SHA pins need not have a remote-tracking branch
    else:
        skill_git._run(["git", "-C", str(repo), "update-ref", tracking, target], env=None)
    return target, chosen


def acquire_agent_parent(parent: Path, acquire, paths, *, new_agent=None):
    """Stage a new clone before it can revive any existing parent projections."""
    import tempfile
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.project_backing import new_install_paths, create_backing_dir
    parent.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".agent-parent-", dir=parent.parent) as temporary:
        stage = Path(temporary) / "checkout"
        acquire(stage)
        head = skill_git.head_sha(stage, env=None)
        if head is None:
            raise InstallError(f"{parent}: acquired repository has no commit")
        chosen = validate_agent_revision(stage, head, paths, new_agent=new_agent)
        with new_install_paths() as claimed:
            create_backing_dir(parent, claimed)  # exclusive claim, foreign paths refused
            stage.replace(parent)  # same filesystem, complete validated tree
    return head, chosen
