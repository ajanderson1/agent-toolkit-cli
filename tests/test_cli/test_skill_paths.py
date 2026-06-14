from pathlib import Path

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_cli.skill_paths import (
    SUPPORTED_HARNESSES,
    _SHORTCUT_TO_AGENT,
    agent_projection_dir,
    canonical_skill_dir,
    harness_projection_dir,
    library_lock_path,
    library_root,
    library_skill_path,
    lock_file_path,
    project_store_root,
)


def test_canonical_skill_dir_global_is_library_path(tmp_path: Path, monkeypatch):
    """v2.2: global canonical delegates to library_skill_path (ignores home)."""
    lib = tmp_path / "mylib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(lib))
    # home is accepted but ignored at global scope.
    home = tmp_path / "home"
    p = canonical_skill_dir("journal", scope="global", home=home, project=None)
    assert p == lib / "journal"


def test_canonical_skill_dir_project(tmp_path: Path, monkeypatch):
    lib = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(lib))
    project = tmp_path / "proj"
    project.mkdir()
    p = canonical_skill_dir("journal", scope="project", home=None, project=project)
    assert p == project_store_root(project) / "journal"


def test_lock_file_path_global_is_library_lock(tmp_path: Path, monkeypatch):
    """v2.2: global lock delegates to library_lock_path (ignores home)."""
    lib = tmp_path / "mylib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(lib))
    home = tmp_path / "home"
    p = lock_file_path(scope="global", home=home, project=None)
    assert p == lib.parent / "skills-lock.json"


def test_lock_file_path_project(tmp_path: Path):
    project = tmp_path / "proj"
    p = lock_file_path(scope="project", home=None, project=project)
    assert p == project / "skills-lock.json"


def test_harness_projection_dir_claude_global(tmp_path: Path):
    # Global scope: harness_projection_dir delegates to agent_projection_dir,
    # which uses cfg.global_skills_dir (resolved at import time against real HOME).
    # The 'home' parameter is NOT used for global-scope agent projections.
    p = harness_projection_dir("claude", "journal", scope="global", home=tmp_path, project=None)
    claude_agent = AGENTS[_SHORTCUT_TO_AGENT["claude"]]
    assert p == claude_agent.global_skills_dir / "journal"


def test_harness_projection_dir_claude_project(tmp_path: Path):
    project = tmp_path / "proj"
    p = harness_projection_dir("claude", "journal", scope="project", home=None, project=project)
    assert p == project / ".claude" / "skills" / "journal"


def test_agent_projection_dir_project_non_universal(tmp_path: Path):
    """agent_projection_dir for project scope uses project / cfg.skills_dir."""
    project = tmp_path / "proj"
    p = agent_projection_dir("claude-code", "journal", scope="project", home=None, project=project)
    assert p == project / ".claude" / "skills" / "journal"


def test_agent_projection_dir_global_uses_catalog(tmp_path: Path):
    """Global scope ignores home, uses cfg.global_skills_dir."""
    p = agent_projection_dir("claude-code", "demo", scope="global", home=tmp_path, project=None)
    claude_agent = AGENTS["claude-code"]
    assert p == claude_agent.global_skills_dir / "demo"


def test_supported_harnesses_includes_known():
    for h in ("claude", "codex", "opencode", "gemini", "pi"):
        assert h in SUPPORTED_HARNESSES


# ---------------------------------------------------------------------------
# library_root / library_skill_path / library_lock_path (Phase 1 / v2.2)
# ---------------------------------------------------------------------------

def test_library_root_default():
    p = library_root(env={})
    assert p == Path.home() / ".agent-toolkit" / "skills"


def test_library_root_honors_env_var(tmp_path: Path):
    custom = tmp_path / "my-skills"
    p = library_root(env={"AGENT_TOOLKIT_SKILLS_ROOT": str(custom)})
    assert p == custom


def test_library_root_ignores_empty_env_var():
    p = library_root(env={"AGENT_TOOLKIT_SKILLS_ROOT": ""})
    assert p == Path.home() / ".agent-toolkit" / "skills"


def test_library_root_ignores_whitespace_only_env_var():
    p = library_root(env={"AGENT_TOOLKIT_SKILLS_ROOT": "   "})
    assert p == Path.home() / ".agent-toolkit" / "skills"


def test_library_skill_path(tmp_path: Path):
    custom = tmp_path / "my-skills"
    p = library_skill_path("foo", env={"AGENT_TOOLKIT_SKILLS_ROOT": str(custom)})
    assert p == custom / "foo"


def test_library_skill_path_default():
    p = library_skill_path("foo", env={})
    assert p == Path.home() / ".agent-toolkit" / "skills" / "foo"


def test_library_lock_path_default():
    p = library_lock_path(env={})
    assert p == Path.home() / ".agent-toolkit" / "skills-lock.json"


def test_library_lock_path_honors_env_var(tmp_path: Path):
    custom = tmp_path / "lib" / "skills"
    p = library_lock_path(env={"AGENT_TOOLKIT_SKILLS_ROOT": str(custom)})
    assert p == tmp_path / "lib" / "skills-lock.json"


def test_parent_clone_path_no_ref(tmp_path):
    from agent_toolkit_cli.skill_paths import parent_clone_path
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    p = parent_clone_path("vamseeachanta", "workspace-hub", ref=None, env=env)
    assert p == tmp_path / "skills" / "_parents" / "vamseeachanta" / "workspace-hub"


def test_parent_clone_path_with_ref(tmp_path):
    from agent_toolkit_cli.skill_paths import parent_clone_path
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    p = parent_clone_path("o", "r", ref="v1.2.3", env=env)
    assert p.name == "r@v1.2.3"
    assert p.parent.name == "o"


def test_parent_clone_path_project_root(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import parent_clone_path, project_parents_root

    lib = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(lib))
    project = tmp_path / "proj"
    project.mkdir()
    root = project_parents_root(project)
    assert root == project_store_root(project)

    p = parent_clone_path("vercel-labs", "agent-browser", ref=None, root=root)
    assert p == root / "_parents" / "vercel-labs" / "agent-browser"

    p_ref = parent_clone_path("o", "r", ref="dev", root=root)
    assert p_ref == root / "_parents" / "o" / "r@dev"


def test_parent_clone_path_default_root_unchanged(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import parent_clone_path

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    p = parent_clone_path("o", "r", ref=None)
    assert p == tmp_path / "lib" / "skills" / "_parents" / "o" / "r"


def test_project_id_stable_and_sanitized(tmp_path):
    from agent_toolkit_cli.skill_paths import project_id

    p = tmp_path / "GitHub" / "ryanair_fares"
    p.mkdir(parents=True)
    pid1 = project_id(p)
    pid2 = project_id(p)
    assert pid1 == pid2, "same path must yield same id"
    assert "/" not in pid1
    prefix, _, suffix = pid1.rpartition("-")
    assert len(suffix) == 6 and all(c in "0123456789abcdef" for c in suffix)
    assert "ryanair_fares" in prefix


def test_project_id_distinct_paths_distinct_ids(tmp_path):
    from agent_toolkit_cli.skill_paths import project_id

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert project_id(a) != project_id(b)


def test_project_store_root_under_library_parent(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import (
        project_store_root, project_id, library_root,
    )

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    project = tmp_path / "proj"
    project.mkdir()
    root = project_store_root(project)
    assert root == library_root().parent / "projects" / project_id(project) / "skills"
    assert root == tmp_path / "lib" / "projects" / project_id(project) / "skills"


def test_canonical_skill_dir_project_uses_store(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import (
        canonical_skill_dir, project_store_root,
    )

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    project = tmp_path / "proj"
    project.mkdir()
    got = canonical_skill_dir("mkdocs", scope="project", project=project)
    assert got == project_store_root(project) / "mkdocs"
    assert ".agents" not in str(got)


def test_project_parents_root_uses_store(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import (
        project_parents_root, project_store_root,
    )

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    project = tmp_path / "proj"
    project.mkdir()
    assert project_parents_root(project) == project_store_root(project)


def _init_repo_with_remote(path, remote_url):
    import subprocess

    from tests.conftest import scrub_git_env
    path.mkdir(parents=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote_url],
        check=True, env=env,
    )


def _init_repo_on_branch(path, remote_url, branch):
    """A repo with one real commit on `branch` and an origin remote.

    Unlike `_init_repo_with_remote`, this checks out a named branch and makes a
    commit, so `current_branch`/`head_sha` return real values — needed to
    exercise the multi-ref and SHA-pin guards. Returns the commit SHA.
    """
    import subprocess

    from tests.conftest import scrub_git_env
    path.mkdir(parents=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote_url],
        check=True, env=env,
    )
    subprocess.run(
        ["git", "-C", str(path), "checkout", "-q", "-b", branch],
        check=True, env=env,
    )
    (path / "f").write_text("x")
    subprocess.run(["git", "-C", str(path), "add", "f"], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", "c"],
        check=True, env=env,
    )
    sha = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()
    return sha


def test_resolve_prefers_suffixed_when_present(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    url = "https://github.com/o/r"
    suffixed = parent_clone_path("o", "r", ref="main", env=env)
    _init_repo_with_remote(suffixed, url)
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url=url, env=env,
    )
    assert got == suffixed


def test_resolve_falls_back_to_bare_on_remote_match(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    url = "https://github.com/o/r"
    bare = parent_clone_path("o", "r", ref=None, env=env)  # legacy layout
    # A real legacy clone has a commit on its branch; the ref-guard reads it.
    _init_repo_on_branch(bare, url + ".git", "main")  # diff URL form, same repo
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url=url, env=env,
    )
    assert got == bare


def test_resolve_rejects_bare_on_remote_mismatch(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_with_remote(bare, "https://github.com/someone/else")
    suffixed = parent_clone_path("o", "r", ref="main", env=env)
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url="https://github.com/o/r", env=env,
    )
    assert got == suffixed  # mismatch => do NOT adopt bare


def test_resolve_returns_suffixed_when_neither_exists(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    suffixed = parent_clone_path("o", "r", ref="main", env=env)
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url="https://github.com/o/r", env=env,
    )
    assert got == suffixed


def test_resolve_ref_none_collapses_to_bare(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_with_remote(bare, "https://github.com/o/r")
    got = resolve_existing_parent_clone(
        "o", "r", ref=None, parent_url="https://github.com/o/r", env=env,
    )
    assert got == bare
    assert got == parent_clone_path("o", "r", ref=None, env=env)


def test_resolve_slash_ref_falls_through_to_suffixed(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    # A flat bare <repo> exists with a matching remote, but ref has a slash —
    # the nested suffixed path is what a slash-ref clone uses, so the flat bare
    # must NOT be adopted.
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_with_remote(bare, "https://github.com/o/r")
    suffixed = parent_clone_path("o", "r", ref="feat/x", env=env)
    got = resolve_existing_parent_clone(
        "o", "r", ref="feat/x", parent_url="https://github.com/o/r", env=env,
    )
    assert got == suffixed
    assert got != bare


def test_resolve_rejects_bare_checked_out_at_different_ref(tmp_path):
    """#412 multi-ref safety: two skills share one monorepo at different
    FLAT refs (the real P1 — both bare and suffixed share a parent dir).

    The legacy bare clone is checked out on `main`. A second skill from the same
    monorepo pins `dev` (also flat, so `bare.parent == suffixed.parent` and the
    slash-ref guard does NOT save us). The resolver must NOT hand the `dev` skill
    the `main` clone — adopting it would let `update`/`reset` mutate or discard
    the tree the `main` skill depends on. It falls through to the suffixed path.
    """
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    url = "https://github.com/o/r"
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_on_branch(bare, url, "main")  # bare lives on main
    suffixed = parent_clone_path("o", "r", ref="dev", env=env)
    assert bare.parent == suffixed.parent  # flat refs => slash-guard inert
    got = resolve_existing_parent_clone(
        "o", "r", ref="dev", parent_url=url, env=env,
    )
    assert got == suffixed  # off-ref bare must NOT be adopted
    assert got != bare


def test_resolve_adopts_bare_checked_out_at_matching_branch(tmp_path):
    """The flip side: when the bare clone IS on the requested branch ref, it is
    the right clone and gets adopted (the legitimate #412 repair case)."""
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    url = "https://github.com/o/r"
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_on_branch(bare, url, "main")
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url=url, env=env,
    )
    assert got == bare


def test_resolve_adopts_bare_pinned_to_matching_sha(tmp_path):
    """SHA-pin case: the bare clone is detached at the pinned commit.

    `current_branch` returns "HEAD" on a detached clone, so a naive branch
    check would wrongly reject it. The guard must compare HEAD sha to the pin
    and adopt when they match — otherwise SHA-pin resolution regresses.
    """
    import subprocess

    from tests.conftest import scrub_git_env
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    url = "https://github.com/o/r"
    bare = parent_clone_path("o", "r", ref=None, env=env)
    sha = _init_repo_on_branch(bare, url, "main")
    # Detach HEAD at the commit, mimicking a SHA-pinned clone.
    subprocess.run(
        ["git", "-C", str(bare), "checkout", "-q", sha],
        check=True, env=scrub_git_env(),
    )
    got = resolve_existing_parent_clone(
        "o", "r", ref=sha, parent_url=url, env=env,
    )
    assert got == bare


def test_resolve_rejects_bare_pinned_to_different_sha(tmp_path):
    """A SHA pin that does not match the bare clone's HEAD must not adopt it."""
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    url = "https://github.com/o/r"
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_on_branch(bare, url, "main")
    other_sha = "0" * 40  # a SHA the bare clone is definitely not on
    suffixed = parent_clone_path("o", "r", ref=other_sha, env=env)
    got = resolve_existing_parent_clone(
        "o", "r", ref=other_sha, parent_url=url, env=env,
    )
    assert got == suffixed
    assert got != bare


def test_resolve_project_scope_adopts_bare_via_root(tmp_path):
    """The project-scope wiring path: resolver is given an explicit `root`
    (project_parents_root) rather than the global library root. The legacy bare
    layout must resolve identically there — status/push pass this root through.
    """
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    root = tmp_path / "store"
    url = "https://github.com/o/r"
    bare = parent_clone_path("o", "r", ref=None, root=root)
    assert bare.parent == (root / "_parents" / "o")  # under the given root
    _init_repo_on_branch(bare, url, "main")
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url=url, root=root,
    )
    assert got == bare
