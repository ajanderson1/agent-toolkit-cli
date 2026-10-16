"""Real filesystem per-harness round trips without any Instructions lock."""
import pytest
from agent_toolkit_cli import instructions_install as ii
from agent_toolkit_cli.instructions_adapters.symlink import CELLS, _pointer_path


@pytest.mark.parametrize("scope", ["project", "global"])
@pytest.mark.parametrize("harness", sorted(CELLS))
def test_pointer_round_trip(tmp_path, monkeypatch, scope, harness):
    if not CELLS[harness][scope]:
        pytest.skip("native reader or unavailable scope")
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    canonical = ii._resolve_canonical(scope, project)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("user instructions\n")
    pointer = _pointer_path(harness, scope, project, home)
    ii.apply(scope=scope, project_root=project, home=home, add_harnesses=(harness,))
    assert pointer.is_symlink() and pointer.read_text() == canonical.read_text()
    ii.uninstall(scope=scope, project_root=project, home=home)
    assert not pointer.is_symlink()
    assert canonical.read_text() == "user instructions\n"
    assert not list(tmp_path.rglob("instructions-lock.json"))
