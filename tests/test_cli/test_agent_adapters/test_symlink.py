"""symlink mechanism: 15 cells write a single .md to a harness-specific agents dir.

Per-cell expected paths sourced from spec addendum Risk Resolution table:
docs/superpowers/specs/2026-05-28-v3-pr2-agent-facade-and-adapters-design.md
"""
from __future__ import annotations

from pathlib import Path

import pytest


# (harness, global-path-template, project-path-template)
# {SLUG} is interpolated; {HOME} is the test's tmp_path; {PROJECT} similarly.
SYMLINK_CELLS = [
    ("augment",        "{HOME}/.augment/agents/{SLUG}.md",
                       "{PROJECT}/.augment/agents/{SLUG}.md"),
    ("claude-code",    "{HOME}/.claude/agents/{SLUG}.md",
                       "{PROJECT}/.claude/agents/{SLUG}.md"),
    ("codebuddy",      "{HOME}/.codebuddy/agents/{SLUG}.md",
                       "{PROJECT}/.codebuddy/agents/{SLUG}.md"),
    ("command-code",   "{HOME}/.commandcode/agents/{SLUG}.md",
                       "{PROJECT}/.commandcode/agents/{SLUG}.md"),
    ("cortex",         "{HOME}/.snowflake/cortex/agents/{SLUG}.md",
                       "{PROJECT}/.cortex/agents/{SLUG}.md"),
    ("cursor",         "{HOME}/.cursor/agents/{SLUG}.md",
                       "{PROJECT}/.cursor/agents/{SLUG}.md"),
    ("droid",          "{HOME}/.factory/droids/{SLUG}.md",
                       "{PROJECT}/.factory/droids/{SLUG}.md"),
    ("forgecode",      "{HOME}/.forge/agents/{SLUG}.md",
                       "{PROJECT}/.forge/agents/{SLUG}.md"),
    ("junie",          "{HOME}/.junie/agents/{SLUG}.md",
                       "{PROJECT}/.junie/agents/{SLUG}.md"),
    ("kode",           "{HOME}/.kode/agents/{SLUG}.md",
                       "{PROJECT}/.claude/agents/{SLUG}.md"),
    ("neovate",        "{HOME}/.neovate/agents/{SLUG}.md",
                       "{PROJECT}/.neovate/agents/{SLUG}.md"),
    ("pi",             "{HOME}/.pi/agent/agents/{SLUG}.md",
                       "{PROJECT}/.pi/agents/{SLUG}.md"),
    ("pochi",          "{HOME}/.pochi/agents/{SLUG}.md",
                       "{PROJECT}/.pochi/agents/{SLUG}.md"),
    ("qoder",          "{HOME}/.qoder/agents/{SLUG}.md",
                       "{PROJECT}/.qoder/agents/{SLUG}.md"),
    ("rovodev",        "{HOME}/.rovodev/subagents/{SLUG}.md",
                       "{PROJECT}/.rovodev/subagents/{SLUG}.md"),
]


@pytest.fixture
def fake_content(tmp_path):
    """Build a minimal canonical content file the adapter will project."""
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text("---\nname: test-agent\ndescription: testing\n---\n\nBody.\n")
    return content


def _expand(template: str, *, home: Path, project: Path, slug: str) -> Path:
    return Path(
        template.replace("{HOME}", str(home))
                .replace("{PROJECT}", str(project))
                .replace("{SLUG}", slug)
    )


@pytest.mark.parametrize("harness, global_tpl, project_tpl", SYMLINK_CELLS)
def test_symlink_install_global(harness, global_tpl, project_tpl, tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for(harness)
    expected = _expand(global_tpl, home=tmp_path, project=tmp_path / "p", slug="test-agent")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == expected
    assert expected.exists()
    # Content matches canonical
    assert expected.read_text() == fake_content.read_text()


@pytest.mark.parametrize("harness, global_tpl, project_tpl", SYMLINK_CELLS)
def test_symlink_install_project(harness, global_tpl, project_tpl, tmp_path, fake_content):
    project = tmp_path / "myproj"
    project.mkdir()
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for(harness)
    expected = _expand(project_tpl, home=tmp_path, project=project, slug="test-agent")
    result = adapter.install("test-agent", fake_content, scope="project", project=project)
    assert result == expected
    assert expected.exists()


@pytest.mark.parametrize("harness, global_tpl, project_tpl", SYMLINK_CELLS)
def test_symlink_uninstall_idempotent(harness, global_tpl, project_tpl, tmp_path, monkeypatch, fake_content):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for(harness)
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    expected = _expand(global_tpl, home=tmp_path, project=tmp_path / "p", slug="test-agent")
    assert expected.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not expected.exists()
    # Second uninstall is a no-op
    adapter.uninstall("test-agent", scope="global", home=tmp_path)


def test_pi_global_path_honours_env_override(tmp_path, monkeypatch, fake_content):
    """pi's $PI_CODING_AGENT_DIR overrides the default ~/.pi/agent/agents/ path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    custom = tmp_path / "custom_pi"
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(custom))
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("pi")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == custom / "agents" / "test-agent.md"
    assert result.exists()
