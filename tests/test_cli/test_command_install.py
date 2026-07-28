from agent_toolkit_cli._install_core import InstallError, InstallPlan
from agent_toolkit_cli.command_adapters.base import write_sidecar
from agent_toolkit_cli.command_install import _current_linked_harnesses, apply


def test_apply_rolls_back_when_later_harness_conflicts(tmp_path):
    canonical = tmp_path / "lib" / "commands" / "demo"
    canonical.mkdir(parents=True)
    (canonical / "COMMAND.md").write_text("demo")
    conflict = tmp_path / ".gemini" / "commands" / "demo.toml"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("hand")
    # Non-standard runs first; gemini fails before standard adopts.
    plan = InstallPlan(
        slug="demo",
        scope="global",
        source=None,
        ref=None,
        add_agents=("claude-code", "gemini-cli"),
        remove_agents=(),
    )
    try:
        apply(plan, home=tmp_path, command_dir_resolver=lambda *a, **k: canonical)
    except InstallError:
        pass
    else:
        raise AssertionError("expected conflict")
    assert not (tmp_path / ".claude" / "commands" / "demo.md").exists()
    assert conflict.read_text() == "hand"


def test_current_linked_harnesses_reports_owned_standard_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    lib = tmp_path / ".agent-toolkit" / "commands" / "demo"
    lib.mkdir(parents=True)
    src = lib / "COMMAND.md"
    src.write_text("demo")
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(src)
    # Adoptable legacy symlink is not yet owned — scanner must not claim it.
    assert _current_linked_harnesses(slug="demo", scope="global", home=tmp_path, project=None) == ()
    write_sidecar(dest, slug="demo", harness="standard", scope="global", canonical=src, content="demo")
    assert _current_linked_harnesses(slug="demo", scope="global", home=tmp_path, project=None) == ("standard",)
