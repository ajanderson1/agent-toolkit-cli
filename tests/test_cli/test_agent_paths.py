"""agent_paths.py facade — public-symbol surface + binding behaviour."""
from __future__ import annotations

from pathlib import Path


# Mirrors test_skill_facade_parity.py § skill_paths but for agent_paths.
AGENT_PATHS_PUBLIC = frozenset({
    "Scope",
    "canonical_agent_dir",
    "lock_file_path",
    "library_root",
    "library_agent_path",
    "library_lock_path",
    "project_id",
    "project_store_root",
    "project_parents_root",
    "parent_clone_path",
    "agent_projection_dir",
    "harness_projection_dir",
    "SUPPORTED_HARNESSES",
})


def test_agent_paths_public_surface_preserved():
    from agent_toolkit_cli import agent_paths
    public = {name for name in dir(agent_paths) if not name.startswith("_")}
    for symbol in AGENT_PATHS_PUBLIC:
        assert symbol in public, f"agent_paths public surface missing: {symbol}"


def test_library_root_resolves_to_agents_subdir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.library_root() == tmp_path / ".agent-toolkit" / "agents"


def test_library_lock_path_resolves(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.library_lock_path() == tmp_path / ".agent-toolkit" / "agents-lock.json"


def test_library_agent_path_for_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.library_agent_path("foo") == tmp_path / ".agent-toolkit" / "agents" / "foo"


def test_canonical_agent_dir_global(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.canonical_agent_dir("foo", scope="global") == tmp_path / ".agent-toolkit" / "agents" / "foo"


def test_canonical_agent_dir_project(tmp_path):
    from agent_toolkit_cli import agent_paths
    project = tmp_path / "proj"
    project.mkdir()
    canonical = agent_paths.canonical_agent_dir("foo", scope="project", project=project)
    # External store; specifics defined by project_store_root.
    assert canonical.name == "foo"
    assert "projects" in str(canonical)


def test_lock_file_path_global(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import agent_paths
    assert agent_paths.lock_file_path(scope="global") == tmp_path / ".agent-toolkit" / "agents-lock.json"


def test_lock_file_path_project(tmp_path):
    from agent_toolkit_cli import agent_paths
    project = tmp_path / "proj"
    project.mkdir()
    # Per AGENT_BINDING.lock_filename = "agents-lock.json"
    assert agent_paths.lock_file_path(scope="project", project=project) == project / "agents-lock.json"


def test_agent_paths_does_not_honour_skill_root_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", "/some/skill/root")
    from agent_toolkit_cli import agent_paths
    # AGENT_TOOLKIT_SKILLS_ROOT must NOT affect agent paths.
    assert agent_paths.library_root() == tmp_path / ".agent-toolkit" / "agents"
