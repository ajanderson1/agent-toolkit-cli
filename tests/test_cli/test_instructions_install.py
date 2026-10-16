"""Explicit planning, aliases, and preservation of source-backed pointers."""
import pytest
from agent_toolkit_cli import instructions_install as ii
from agent_toolkit_cli.instructions_adapters.symlink import PointerConflictError
from tests.test_cli.test_instructions_lockless import snapshot


@pytest.fixture
def project(tmp_path):
    (tmp_path / "AGENTS.md").write_text("canonical\n")
    return tmp_path


def test_empty_intent_is_read_only_noop(project):
    (project / "CLAUDE.md").symlink_to("AGENTS.md")
    before = snapshot(project)
    assert ii.plan(scope="project", project_root=project, home=None).actions == []
    assert ii.apply(scope="project", project_root=project, home=None).actions == []
    assert snapshot(project) == before


def test_selected_removal_preserves_other_pointers(project):
    ii.apply(scope="project", project_root=project, home=None, add_harnesses=("claude-code", "gemini-cli"))
    ii.apply(scope="project", project_root=project, home=None, remove_harnesses=("claude-code",))
    assert not (project / "CLAUDE.md").is_symlink()
    assert (project / "GEMINI.md").is_symlink()


def test_aliases_coalesce_by_physical_slot(project):
    p = ii.apply(scope="project", project_root=project, home=None, add_harnesses=("augment", "claude-code"))
    assert len(p.actions) == 1
    assert (project / "CLAUDE.md").is_symlink()
    assert ii.apply(scope="project", project_root=project, home=None, add_harnesses=("claude-code",)).actions[0].action == "noop-already-correct"


def test_opposing_shared_slot_intents_refused_before_any_write(project):
    before = snapshot(project)
    with pytest.raises(PointerConflictError, match="opposing"):
        ii.apply(scope="project", project_root=project, home=None,
                 add_harnesses=("gemini-cli", "augment"), remove_harnesses=("claude-code",))
    assert snapshot(project) == before


@pytest.mark.parametrize("harness", ["missing-harness", "pi"])
def test_invalid_or_native_harness_preflight(project, harness):
    before = snapshot(project)
    with pytest.raises((KeyError, ValueError)):
        ii.apply(scope="project", project_root=project, home=None, add_harnesses=("claude-code", harness))
    assert snapshot(project) == before


def test_project_scope_never_falls_back_to_global():
    with pytest.raises(ValueError, match="project_root"):
        ii.plan(scope="project", project_root=None, home=None)
