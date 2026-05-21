from pathlib import Path

from agent_toolkit_cli.skill_paths import (
    SUPPORTED_HARNESSES,
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
    home = tmp_path / "home"
    p = harness_projection_dir("claude", "journal", scope="global", home=home, project=None)
    assert p == home / ".claude" / "skills" / "journal"


def test_harness_projection_dir_claude_project(tmp_path: Path):
    project = tmp_path / "proj"
    p = harness_projection_dir("claude", "journal", scope="project", home=None, project=project)
    assert p == project / ".claude" / "skills" / "journal"


def test_supported_harnesses_includes_known():
    for h in ("claude", "codex", "opencode", "gemini", "pi"):
        assert h in SUPPORTED_HARNESSES
