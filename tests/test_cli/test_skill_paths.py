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
)


def test_canonical_skill_dir_global_is_library_path(tmp_path: Path, monkeypatch):
    """v2.2: global canonical delegates to library_skill_path (ignores home)."""
    lib = tmp_path / "mylib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(lib))
    # home is accepted but ignored at global scope.
    home = tmp_path / "home"
    p = canonical_skill_dir("journal", scope="global", home=home, project=None)
    assert p == lib / "journal"


def test_canonical_skill_dir_project(tmp_path: Path):
    project = tmp_path / "proj"
    p = canonical_skill_dir("journal", scope="project", home=None, project=project)
    assert p == project / ".agents" / "skills" / "journal"


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


def test_parent_clone_path_project_root(tmp_path):
    from agent_toolkit_cli.skill_paths import parent_clone_path, project_parents_root

    project = tmp_path / "proj"
    root = project_parents_root(project)
    assert root == project / ".agents" / "skills"

    p = parent_clone_path("vercel-labs", "agent-browser", ref=None, root=root)
    assert p == project / ".agents" / "skills" / "_parents" / "vercel-labs" / "agent-browser"

    p_ref = parent_clone_path("o", "r", ref="dev", root=root)
    assert p_ref == project / ".agents" / "skills" / "_parents" / "o" / "r@dev"


def test_parent_clone_path_default_root_unchanged(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import parent_clone_path, library_root

    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    p = parent_clone_path("o", "r", ref=None)
    assert p == library_root() / "_parents" / "o" / "r"
