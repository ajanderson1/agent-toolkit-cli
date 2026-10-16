"""Instructions intentionally has no source-backed lock binding (#525)."""
from agent_toolkit_cli import _paths_core, instructions_paths


def test_instructions_has_no_installation_registry():
    assert not hasattr(_paths_core, "INSTRUCTIONS_BINDING")
    for name in ("library_lock_path", "project_lock_path", "lock_file_path"):
        assert not hasattr(instructions_paths, name)


def test_skills_override_does_not_redirect_instruction_source(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "elsewhere"))
    assert instructions_paths.global_canonical_agents_md() == tmp_path / ".agent-toolkit/AGENTS.md"


def test_legacy_instruction_file_does_not_change_default_scope(tmp_path):
    (tmp_path / "instructions-lock.json").write_text("obsolete")
    assert _paths_core.default_scope(tmp_path) == "global"
