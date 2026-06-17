import os

import pytest

from agent_toolkit_cli.command_adapters import get_adapter
from agent_toolkit_cli.command_install import apply
from agent_toolkit_cli._install_core import InstallPlan, InstallError


def test_claude_command_destination_global(tmp_path):
    adapter = get_adapter("claude-code")
    dest = adapter.destination("demo", scope="global", home=tmp_path, project=None)
    assert dest == tmp_path / ".claude" / "commands" / "demo.md"


def test_pi_command_destination_project(tmp_path):
    adapter = get_adapter("pi")
    project = tmp_path / "repo"
    dest = adapter.destination("demo", scope="project", home=None, project=project)
    assert dest == project / ".pi" / "prompts" / "demo.md"


def test_codex_project_scope_is_refused(tmp_path):
    adapter = get_adapter("codex")
    with pytest.raises(ValueError, match="Codex commands are global-only"):
        adapter.destination("demo", scope="project", home=None, project=tmp_path)


def test_unknown_and_synthetic_harnesses_rejected():
    with pytest.raises(ValueError, match="unsupported command harness"):
        get_adapter("unknown")
    with pytest.raises(ValueError, match="unsupported command harness"):
        get_adapter("standard-command")


def test_markdown_install_refuses_unmanaged_conflict(tmp_path):
    canonical = tmp_path / "lib" / "commands" / "demo"
    canonical.mkdir(parents=True)
    (canonical / "COMMAND.md").write_text("demo")
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("hand")
    plan = InstallPlan(slug="demo", scope="global", source=None, ref=None, add_agents=("claude-code",), remove_agents=())
    with pytest.raises(InstallError, match="unmanaged command exists"):
        apply(plan, home=tmp_path, command_dir_resolver=lambda *a, **k: canonical)
    assert dest.read_text() == "hand"


def test_markdown_install_refuses_symlinked_command_md(tmp_path):
    target = tmp_path / "real.md"
    target.write_text("demo")
    canonical = tmp_path / "lib" / "commands" / "demo"
    canonical.mkdir(parents=True)
    os.symlink(target, canonical / "COMMAND.md")
    plan = InstallPlan(slug="demo", scope="global", source=None, ref=None, add_agents=("claude-code",), remove_agents=())
    with pytest.raises(InstallError, match="must be a regular file"):
        apply(plan, home=tmp_path, command_dir_resolver=lambda *a, **k: canonical)
