import pytest

from agent_toolkit_cli.command_adapters import get_adapter
from agent_toolkit_cli.command_adapters.gemini import render_gemini_toml


def test_gemini_command_destination_global(tmp_path):
    adapter = get_adapter("gemini-cli")
    dest = adapter.destination("demo", scope="global", home=tmp_path, project=None)
    assert dest == tmp_path / ".gemini" / "commands" / "demo.toml"


def test_gemini_render_translates_arguments():
    text = "---\ndescription: Demo\nargument-hint: [issue]\n---\nFix: $ARGUMENTS\n"
    rendered = render_gemini_toml(text)
    assert 'description = "Demo"' in rendered
    assert 'prompt = ' in rendered
    assert "Fix: {{args}}" in rendered


def test_gemini_install_writes_sidecar_and_uninstall_preserves_hand_file(tmp_path):
    src = tmp_path / "COMMAND.md"
    src.write_text("hello $ARGUMENTS")
    adapter = get_adapter("gemini-cli")
    dest = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert dest.read_text().count("{{args}}") == 1
    assert dest.with_suffix(dest.suffix + ".attk").exists()
    assert adapter.uninstall("demo", scope="global", home=tmp_path, project=None) == dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("hand")
    assert adapter.uninstall("demo", scope="global", home=tmp_path, project=None) is None
    assert dest.read_text() == "hand"


def test_gemini_injection_tokens_warn(tmp_path, recwarn):
    src = tmp_path / "COMMAND.md"
    src.write_text("run !{echo hi} and @{file}")
    adapter = get_adapter("gemini-cli")
    adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert any("Gemini command injection token" in str(w.message) for w in recwarn)
