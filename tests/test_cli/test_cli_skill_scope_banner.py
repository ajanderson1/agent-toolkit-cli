"""Tests for #413 — implicit-scope reminder banner + 4-tuple resolution."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.commands.skill._common import scope_and_roots


def test_scope_and_roots_explicit_flags_are_not_implicit(tmp_path: Path):
    g = scope_and_roots(True, False, None, read_only=True)
    p = scope_and_roots(False, True, tmp_path, read_only=True)
    assert g == ("global", Path.home(), None, False)
    assert p == ("project", None, tmp_path, False)


def test_scope_and_roots_implicit_project_when_cwd_lock(tmp_path: Path):
    (tmp_path / "skills-lock.json").write_text("{}")
    scope, home, root, implicit = scope_and_roots(
        False, False, tmp_path, read_only=True,
    )
    assert (scope, home, root, implicit) == ("project", None, tmp_path, True)


def test_scope_and_roots_implicit_global_when_no_cwd_lock(tmp_path: Path):
    scope, home, root, implicit = scope_and_roots(
        False, False, tmp_path, read_only=True,
    )
    assert (scope, home, root, implicit) == ("global", Path.home(), None, True)


# ── scope_banner helper ─────────────────────────────────────────────────────

import click  # noqa: E402
from click.testing import CliRunner  # noqa: E402

from agent_toolkit_cli.commands.skill._common import scope_banner  # noqa: E402


def _run_banner(**kwargs) -> tuple[str, str]:
    """Invoke scope_banner inside a tiny Click command; return (stdout, stderr).

    Click 8.2+ separates stdout/stderr by default — no mix_stderr arg exists.
    """
    @click.command()
    def cmd():
        scope_banner(**kwargs)

    runner = CliRunner()
    result = runner.invoke(cmd, [])
    assert result.exit_code == 0
    return result.stdout, result.stderr


def test_banner_prints_on_implicit_project_to_stdout_by_default():
    stdout, stderr = _run_banner(
        scope="project", implicit=True,
        lock_path="/x/skills-lock.json", count=6,
    )
    assert stderr == ""                       # default: not on stderr
    assert "project scope" in stdout
    assert "/x/skills-lock.json" in stdout
    assert "6 skills" in stdout
    assert "Pass -g for the global library" in stdout


def test_banner_routes_to_stderr_when_err_true():
    stdout, stderr = _run_banner(
        scope="project", implicit=True,
        lock_path="/x/skills-lock.json", count=6, err=True,
    )
    assert stdout == ""                       # nothing on stdout
    assert "project scope" in stderr


def test_banner_singular_noun_for_one_skill():
    stdout, _ = _run_banner(
        scope="project", implicit=True,
        lock_path="/x/skills-lock.json", count=1,
    )
    assert "(1 skill)" in stdout
    assert "1 skills" not in stdout


def test_banner_prints_on_empty_project_lock():
    stdout, _ = _run_banner(
        scope="project", implicit=True,
        lock_path="/x/skills-lock.json", count=0,
    )
    assert "0 skills" in stdout


def test_banner_silent_on_implicit_global():
    stdout, stderr = _run_banner(
        scope="global", implicit=True, lock_path=None, count=12,
    )
    assert stdout == "" and stderr == ""


def test_banner_silent_on_explicit_project():
    stdout, stderr = _run_banner(
        scope="project", implicit=False,
        lock_path="/x/skills-lock.json", count=6,
    )
    assert stdout == "" and stderr == ""


# ── per-verb wiring (CLI level) ─────────────────────────────────────────────

import json  # noqa: E402

from agent_toolkit_cli.cli import main  # noqa: E402


def _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox, slug="demo"):
    """Add a skill to the library and install it into a project, so the
    project gets a non-empty skills-lock.json. Returns the project path."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    assert runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", slug,
    ]).exit_code == 0
    assert runner.invoke(main, [
        "--project", str(project), "skill", "install", slug,
        "--scope", "project", "--agents", "claude-code",
    ]).exit_code == 0
    return project


def test_list_json_banner_on_stderr_stdout_clean(
    git_sandbox, tmp_path, monkeypatch,
):
    runner = CliRunner()
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    # No -g/-p: implicit project (project root has skills-lock.json).
    result = runner.invoke(main, [
        "--project", str(project), "skill", "list", "--json",
    ])
    assert result.exit_code == 0, result.stderr
    # stdout is pristine JSON; banner is on stderr (the --json exception).
    assert json.loads(result.stdout)
    assert "project scope" in result.stderr


def test_list_table_banner_on_stdout(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner()
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "list"])
    assert result.exit_code == 0, result.stderr
    assert "project scope" in result.stdout   # human path → stdout


def test_list_explicit_global_no_banner(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner()
    _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0, result.stderr
    assert "project scope" not in result.stdout
    assert "project scope" not in result.stderr


def test_status_implicit_project_banner_on_stdout(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner()
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "status"])
    assert result.exit_code == 0, result.stderr
    assert "project scope" in result.stdout


def test_status_explicit_project_no_banner(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner()
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "status", "-p"])
    assert result.exit_code == 0, result.stderr
    assert "project scope" not in result.stdout  # explicit -p → no reminder


def test_update_implicit_project_banner_on_stdout(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner()
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "update"])
    # Exit code may be 0 (clean) — we only assert the banner is on stdout.
    assert "project scope" in result.stdout


def test_reset_implicit_project_banner_on_stdout(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner()
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "reset", "demo"])
    assert "project scope" in result.stdout


def test_push_implicit_project_banner_on_stdout(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner()
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "push", "demo"])
    assert "project scope" in result.stdout


def test_doctor_implicit_project_banner_on_stdout(git_sandbox, tmp_path, monkeypatch):
    runner = CliRunner()
    project = _seed_project_lock(runner, tmp_path, monkeypatch, git_sandbox)
    result = runner.invoke(main, ["--project", str(project), "skill", "doctor"])
    assert "project scope" in result.stdout
