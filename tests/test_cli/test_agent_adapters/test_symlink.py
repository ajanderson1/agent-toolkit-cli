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


@pytest.fixture(autouse=True)
def _clean_pi_env(monkeypatch):
    """Every test starts with PI_CODING_AGENT_DIR unset — pi-specific tests
    that need the override set it explicitly. Prevents dev-shell env from
    breaking the parametrized pi cell (pi-template default falls back to
    home= when env is absent)."""
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)


@pytest.mark.parametrize("harness, global_tpl, project_tpl", SYMLINK_CELLS)
def test_symlink_install_global(harness, global_tpl, project_tpl, tmp_path, fake_content):
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
def test_symlink_uninstall_idempotent(harness, global_tpl, project_tpl, tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for(harness)
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    expected = _expand(global_tpl, home=tmp_path, project=tmp_path / "p", slug="test-agent")
    assert expected.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not expected.exists()
    # Second uninstall is a no-op
    adapter.uninstall("test-agent", scope="global", home=tmp_path)


def test_symlink_uninstall_removes_orphan_sentinel(tmp_path, fake_content):
    """#361: uninstall must also remove a leftover .attk sentinel — an
    orphaned sentinel would later authorize a silent clobber of a file the
    user re-authored at this path (via _guard_foreign). kode at GLOBAL scope
    (.kode/agents/) is deliberately NOT the standard slot, so this exercises
    the plain symlink adapter, not the standard adapter."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, symlink

    adapter = symlink.adapter_for("kode")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    sentinel = _sentinel_path(dest)
    sentinel.write_text("")
    assert dest.exists() and sentinel.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not dest.exists()
    assert not sentinel.exists(), "orphaned .attk sentinel after uninstall"


def test_pi_global_path_honours_env_override(tmp_path, monkeypatch, fake_content):
    """pi's $PI_CODING_AGENT_DIR overrides the default ~/.pi/agent/agents/ path."""
    custom = tmp_path / "custom_pi"
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(custom))
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("pi")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == custom / "agents" / "test-agent.md"
    assert result.exists()


# ── Fail-loud behaviour (regressions if the silent-fallback branches return) ──

def test_adapter_for_unknown_harness_raises():
    """symlink.adapter_for must raise UnknownAgentError for any harness
    not in the CELLS dict — independent of the dispatcher layer's check."""
    from agent_toolkit_cli.agent_adapters import symlink
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    with pytest.raises(UnknownAgentError):
        symlink.adapter_for("nonexistent-harness-xyz")


def test_install_with_invalid_scope_raises(tmp_path, fake_content):
    """Bad scope must raise ValueError (not bare KeyError) so call sites see
    a domain-shaped error, not implementation-shape leakage."""
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("claude-code")
    with pytest.raises(ValueError, match="global.*project"):
        adapter.install("test", fake_content, scope="globall", home=tmp_path)


def test_install_global_without_home_raises(tmp_path, fake_content):
    """Fail-loud: scope='global' without home= would silently write to
    './{HOME}/.claude/agents/...' under cwd. Must raise ValueError."""
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("claude-code")
    with pytest.raises(ValueError, match="requires home="):
        adapter.install("test", fake_content, scope="global", home=None)


def test_install_project_without_project_raises(tmp_path, fake_content):
    """Fail-loud: scope='project' without project= would silently write to
    './{PROJECT}/.claude/agents/...' under cwd. Must raise ValueError."""
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("claude-code")
    with pytest.raises(ValueError, match="requires project="):
        adapter.install("test", fake_content, scope="project", project=None)


def test_pi_install_global_without_env_or_home_raises(tmp_path, fake_content):
    """Fail-loud: pi template needs either env override OR explicit home=.
    Without both, must raise ValueError — not silently fall back to the
    real user's Path.home()."""
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("pi")
    with pytest.raises(ValueError, match="PI_CODING_AGENT_DIR"):
        adapter.install("test", fake_content, scope="global", home=None)
