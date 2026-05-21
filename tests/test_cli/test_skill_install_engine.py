"""Tests for catalog-aware plan() + apply() with universal/non-universal
skip rules."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.skill_install import (
    InstallError, InstallPlan, LockMismatchError,
    _should_skip_symlink, apply, ensure_project_canonical, plan,
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
    """codex is universal → per-agent symlink skipped at global scope.

    v2.2: individual universal agents (codex, gemini-cli, etc.) skip their
    per-agent symlink. The single ~/.agents/skills/<slug> bundle symlink is
    created separately via the "universal" token in apply(), not per-agent.
    """
    skip, reason = _should_skip_symlink(
        agent_name="codex", scope="global", project=None,
    )
    assert skip is True
    assert reason == "universal-global"


def test_skip_rule_project_universal(tmp_path):
    """codex is universal → project install skips symlink.

    Project canonical at <project>/.agents/skills/<slug>/ IS the install for
    universal agents. No additional symlink is created.
    """
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


# ── ensure_project_canonical tests ─────────────────────────────────────────


def _seed_global_lock(library_root: Path, upstream: Path, slug: str) -> None:
    """Write a minimal v1 global lock entry so ensure_project_canonical can read it."""
    from agent_toolkit_cli.skill_lock import LockEntry, LockFile, add_entry, write_lock
    lock_path = library_root.parent / "skills-lock.json"
    entry = LockEntry(
        source=str(upstream),
        source_type="local",
        ref=None,
        skill_path="SKILL.md",
        upstream_sha=None,
        local_sha=None,
    )
    write_lock(lock_path, add_entry(LockFile(version=1, skills={}), slug, entry))


def test_ensure_project_canonical_clones_when_absent(git_sandbox, tmp_path, monkeypatch):
    """ensure_project_canonical clones the project canonical when it doesn't exist."""
    library_root = tmp_path / "lib" / "skills"
    library_root.mkdir(parents=True)
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    global_lock_path = library_root.parent / "skills-lock.json"
    _seed_global_lock(library_root, git_sandbox.upstream, "demo")

    result = ensure_project_canonical(
        slug="demo",
        project=project,
        global_lock_path=global_lock_path,
        env=git_sandbox.env,
    )

    assert result == project / ".agents" / "skills" / "demo"
    assert result.is_dir() and not result.is_symlink()
    assert (result / "SKILL.md").exists()


def test_ensure_project_canonical_idempotent(git_sandbox, tmp_path, monkeypatch):
    """ensure_project_canonical is idempotent when the project canonical already exists."""
    library_root = tmp_path / "lib" / "skills"
    library_root.mkdir(parents=True)
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    global_lock_path = library_root.parent / "skills-lock.json"
    _seed_global_lock(library_root, git_sandbox.upstream, "demo")

    # First call clones.
    p1 = ensure_project_canonical(
        slug="demo", project=project,
        global_lock_path=global_lock_path, env=git_sandbox.env,
    )
    # Second call returns the existing path without error.
    p2 = ensure_project_canonical(
        slug="demo", project=project,
        global_lock_path=global_lock_path, env=git_sandbox.env,
    )
    assert p1 == p2
    assert p2.is_dir()


def test_ensure_project_canonical_raises_if_slug_missing(tmp_path):
    """ensure_project_canonical raises InstallError when slug is absent from global lock."""
    library_root = tmp_path / "lib" / "skills"
    library_root.mkdir(parents=True)
    project = tmp_path / "proj"
    project.mkdir()

    global_lock_path = library_root.parent / "skills-lock.json"
    # Don't seed any entry — the lock file doesn't exist.

    with pytest.raises(InstallError, match="not in global library"):
        ensure_project_canonical(
            slug="nonexistent", project=project,
            global_lock_path=global_lock_path, env=None,
        )


def test_ensure_project_canonical_writes_project_lock(git_sandbox, tmp_path, monkeypatch):
    """ensure_project_canonical writes the project lock entry on first clone."""
    import json
    library_root = tmp_path / "lib" / "skills"
    library_root.mkdir(parents=True)
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    global_lock_path = library_root.parent / "skills-lock.json"
    _seed_global_lock(library_root, git_sandbox.upstream, "demo")

    ensure_project_canonical(
        slug="demo", project=project,
        global_lock_path=global_lock_path, env=git_sandbox.env,
    )

    project_lock_path = project / "skills-lock.json"
    assert project_lock_path.exists(), "project lock must be written"
    data = json.loads(project_lock_path.read_text())
    assert "demo" in data.get("skills", {}), "demo must appear in project lock"
