"""User-owned Instructions paths are independent of installation state."""
from agent_toolkit_cli import instructions_paths


def test_global_canonical_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert instructions_paths.library_root() == tmp_path / ".agent-toolkit/instructions"
    assert instructions_paths.global_canonical_agents_md() == tmp_path / ".agent-toolkit/AGENTS.md"
    assert not (tmp_path / ".agent-toolkit").exists()


def test_project_canonical_path(tmp_path):
    assert instructions_paths.project_canonical_agents_md(tmp_path) == tmp_path / "AGENTS.md"
