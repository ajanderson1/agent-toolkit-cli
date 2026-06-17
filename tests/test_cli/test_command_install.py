from agent_toolkit_cli.command_install import _current_linked_harnesses, apply
from agent_toolkit_cli._install_core import InstallPlan, InstallError


def test_apply_rolls_back_when_later_harness_conflicts(tmp_path):
    canonical = tmp_path / "lib" / "commands" / "demo"
    canonical.mkdir(parents=True)
    (canonical / "COMMAND.md").write_text("demo")
    conflict = tmp_path / ".gemini" / "commands" / "demo.toml"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("hand")
    plan = InstallPlan(slug="demo", scope="global", source=None, ref=None, add_agents=("claude-code", "gemini-cli"), remove_agents=())
    try:
        apply(plan, home=tmp_path, command_dir_resolver=lambda *a, **k: canonical)
    except InstallError:
        pass
    else:
        raise AssertionError("expected conflict")
    assert not (tmp_path / ".claude" / "commands" / "demo.md").exists()
    assert conflict.read_text() == "hand"


def test_current_linked_harnesses_detects_projection(tmp_path):
    target = tmp_path / "COMMAND.md"
    target.write_text("demo")
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(target)
    assert _current_linked_harnesses(slug="demo", scope="global", home=tmp_path, project=None) == ("claude-code",)
