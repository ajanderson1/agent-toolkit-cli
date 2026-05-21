from pathlib import Path

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_cli.skill_paths import (
    SUPPORTED_HARNESSES,
    _SHORTCUT_TO_AGENT,
    agent_projection_dir,
    canonical_skill_dir,
    harness_projection_dir,
    lock_file_path,
)


def test_canonical_skill_dir_global(tmp_path: Path):
    home = tmp_path / "home"
    p = canonical_skill_dir("journal", scope="global", home=home, project=None)
    assert p == home / ".agents" / "skills" / "journal"


def test_canonical_skill_dir_project(tmp_path: Path):
    project = tmp_path / "proj"
    p = canonical_skill_dir("journal", scope="project", home=None, project=project)
    assert p == project / ".agents" / "skills" / "journal"


def test_lock_file_path_global(tmp_path: Path):
    home = tmp_path / "home"
    p = lock_file_path(scope="global", home=home, project=None)
    assert p == home / ".agents" / ".skill-lock.json"


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
