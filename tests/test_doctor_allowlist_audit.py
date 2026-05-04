"""Tests for the allowlist-audit doctor group (issue #10)."""
from __future__ import annotations

import pytest

from agent_toolkit.doctor import allowlist_audit
from agent_toolkit.doctor.result import Status


@pytest.fixture
def env(tmp_path, monkeypatch, seed_toolkit, seed_skill):
    """Toolkit with one skill, empty home, no allowlist."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    toolkit_root = seed_toolkit(tmp_path)
    seed_skill(toolkit_root, "alpha", ["claude"])
    return {"home": home, "toolkit_root": toolkit_root}


def test_clean_returns_ok(env):
    result = allowlist_audit.run(env["toolkit_root"], project_root=env["home"])
    assert result.status == Status.OK
    assert result.name == "allowlist-audit"


def test_allowlist_phantom_slug_warns(env):
    home = env["home"]
    yaml_path = home / ".agent-toolkit.yaml"
    yaml_path.write_text(
        "skills:\n  - alpha\n  - phantom\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    result = allowlist_audit.run(env["toolkit_root"], project_root=home)
    assert result.status == Status.WARN
    assert any("phantom" in f for f in result.findings)
    # alpha exists — should not be flagged as missing
    assert not any("alpha" in f and "not in the toolkit" in f for f in result.findings)


def test_project_allowlist_phantom_slug_warns(env, tmp_path):
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / ".agent-toolkit.yaml").write_text(
        "skills:\n  - phantom\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    result = allowlist_audit.run(env["toolkit_root"], project_root=proj)
    assert result.status == Status.WARN
    assert any("phantom" in f for f in result.findings)


def test_cross_toolkit_symlink_warns(env, tmp_path, seed_toolkit, seed_skill):
    home = env["home"]
    other_parent = tmp_path / "other-parent"
    other_parent.mkdir()
    other_toolkit = seed_toolkit(other_parent)
    seed_skill(other_toolkit, "alpha", ["claude"])
    user_skills = home / ".claude" / "skills"
    user_skills.mkdir(parents=True)
    (user_skills / "alpha").symlink_to(other_toolkit / "skills" / "alpha")

    result = allowlist_audit.run(env["toolkit_root"], project_root=home)
    assert result.status == Status.WARN
    assert any("alpha" in f and "different toolkit" in f for f in result.findings)


def test_symlink_into_configured_toolkit_does_not_warn(env):
    home = env["home"]
    user_skills = home / ".claude" / "skills"
    user_skills.mkdir(parents=True)
    (user_skills / "alpha").symlink_to(env["toolkit_root"] / "skills" / "alpha")

    result = allowlist_audit.run(env["toolkit_root"], project_root=home)
    assert not any("different toolkit" in f for f in result.findings)


def test_broken_symlink_not_double_reported(env):
    """allowlist-audit must not report broken symlinks (symlink-integrity owns that)."""
    home = env["home"]
    user_skills = home / ".claude" / "skills"
    user_skills.mkdir(parents=True)
    (user_skills / "alpha").symlink_to(env["toolkit_root"] / "skills" / "nonexistent")

    result = allowlist_audit.run(env["toolkit_root"], project_root=home)
    # Look for the failure-mode words in *findings about the alpha symlink*,
    # not in path strings (which can incidentally contain test names).
    alpha_findings = [f for f in result.findings if "alpha" in f and "/.claude/" in f]
    assert not any("dangling" in f.lower() for f in alpha_findings)
    assert not any("broken" in f.lower() for f in alpha_findings)
