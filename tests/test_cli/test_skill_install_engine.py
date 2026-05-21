"""Tests for catalog-aware plan() + apply() with universal/non-universal
skip rules."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.skill_install import (
    InstallError, InstallPlan, LockMismatchError,
    _should_skip_symlink, apply, plan,
)
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir, agent_projection_dir, lock_file_path,
)
from agent_toolkit_cli.skill_source import ParsedSource


def _src(path: Path) -> ParsedSource:
    return ParsedSource(
        type="local", url=str(path), owner_repo=None,
        ref=None, subpath=None,
    )


# ── Skip-rule unit tests ────────────────────────────────────────────────


def test_skip_rule_global_universal(tmp_path):
    """codex is universal → global install skips symlink."""
    skip, reason = _should_skip_symlink(
        agent_name="codex", scope="global", project=None,
    )
    assert skip is True
    assert reason == "universal-global"


def test_skip_rule_project_universal(tmp_path):
    """codex is universal → project install also skips symlink.

    For universal agents cfg.skills_dir == '.agents/skills', which equals the
    canonical dir. Creating a symlink from the canonical path to itself is not
    meaningful, so both scopes skip the symlink creation."""
    skip, reason = _should_skip_symlink(
        agent_name="codex", scope="project", project=tmp_path,
    )
    assert skip is True
    assert reason == "universal-project"


def test_skip_rule_global_non_universal(tmp_path):
    """claude-code is non-universal → global install creates symlink."""
    skip, _ = _should_skip_symlink(
        agent_name="claude-code", scope="global", project=None,
    )
    assert skip is False


def test_skip_rule_project_non_universal_no_dir(tmp_path):
    """windsurf is non-universal; if .windsurf/ doesn't exist in project, skip."""
    skip, reason = _should_skip_symlink(
        agent_name="windsurf", scope="project", project=tmp_path,
    )
    assert skip is True
    assert reason == "agent-root-absent"


def test_skip_rule_project_non_universal_dir_exists(tmp_path):
    """windsurf with .windsurf/ present in project → symlink created."""
    (tmp_path / ".windsurf").mkdir()
    skip, _ = _should_skip_symlink(
        agent_name="windsurf", scope="project", project=tmp_path,
    )
    assert skip is False


# ── apply() integration tests ───────────────────────────────────────────


def test_apply_global_claude_creates_symlink(git_sandbox):
    """Global install + claude-code (non-universal) → skipped because global
    scope uses cfg.global_skills_dir (real ~/.claude), which would pollute
    the developer's machine."""
    pytest.skip(
        "global-scope tests would touch the real ~/.claude; covered by "
        "test_apply_project_*"
    )


def test_apply_project_claude_creates_symlink_when_dir_exists(git_sandbox, tmp_path):
    """Project install + claude-code (non-universal) → symlink in project."""
    home = Path(git_sandbox.env["HOME"])
    src = _src(git_sandbox.upstream)
    project = tmp_path / "myproj"
    project.mkdir()
    (project / ".claude").mkdir()  # satisfy skip-rule 2
    p = InstallPlan(
        slug="demo", scope="project", source=src, ref=None,
        add_agents=("claude-code",), remove_agents=(),
    )
    result = apply(p, home=home, project=project, env=git_sandbox.env)
    link = agent_projection_dir(
        "claude-code", "demo", scope="project", home=home, project=project,
    )
    assert link.is_symlink()
    assert "claude-code" not in result.skipped


def test_apply_project_windsurf_skipped_when_dir_absent(git_sandbox, tmp_path):
    """Project install + windsurf (non-universal); no .windsurf/ → skipped."""
    home = Path(git_sandbox.env["HOME"])
    src = _src(git_sandbox.upstream)
    project = tmp_path / "myproj"
    project.mkdir()
    p = InstallPlan(
        slug="demo", scope="project", source=src, ref=None,
        add_agents=("windsurf",), remove_agents=(),
    )
    result = apply(p, home=home, project=project, env=git_sandbox.env)
    link = agent_projection_dir(
        "windsurf", "demo", scope="project", home=home, project=project,
    )
    assert not link.exists()
    assert "windsurf" in result.skipped


def test_apply_project_codex_skipped_universal(git_sandbox, tmp_path):
    """Project install + codex (universal) → skipped because the canonical
    path equals the agent projection path for universal agents."""
    home = Path(git_sandbox.env["HOME"])
    src = _src(git_sandbox.upstream)
    project = tmp_path / "myproj"
    project.mkdir()
    p = InstallPlan(
        slug="demo", scope="project", source=src, ref=None,
        add_agents=("codex",), remove_agents=(),
    )
    result = apply(p, home=home, project=project, env=git_sandbox.env)
    canonical = canonical_skill_dir(
        "demo", scope="project", home=home, project=project,
    )
    # The canonical is a real directory (git clone), not a symlink.
    assert canonical.is_dir() and not canonical.is_symlink()
    # codex is universal → symlink creation was skipped.
    assert "codex" in result.skipped


def test_plan_unknown_agent_raises():
    """plan() with bogus agent name raises UnknownAgentError."""
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    with pytest.raises(UnknownAgentError):
        plan(
            slug="x", scope="global",
            target_agents=("not-a-real-agent",),
            home=Path("/tmp"), project=None,
        )
