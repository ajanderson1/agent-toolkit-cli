from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_tui.skill_state import SkillRow, build_skill_rows


def _add_demo_project(runner, upstream_path, project):
    (project / ".claude").mkdir(exist_ok=True)
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "add", str(upstream_path), "--slug", "demo", "-p",
        "--agent", "claude-code",
    ])


def test_build_skill_rows_clean(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    (project / ".claude").mkdir(exist_ok=True)
    CliRunner().invoke(main, [
        "--project", str(project),
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-p",
        "--agent", "claude-code",
    ])
    _add_demo_project(CliRunner(), git_sandbox.upstream, project)
    rows = build_skill_rows(scope="project", home=None, project=project)
    assert any(r.slug == "demo" and r.state == "clean" for r in rows)


def test_build_skill_rows_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    _add_demo_project(CliRunner(), git_sandbox.upstream, project)
    (project / ".agents" / "skills" / "demo" / "SKILL.md").write_text("edit\n")
    rows = build_skill_rows(scope="project", home=None, project=project)
    assert rows[0].state == "dirty"


def test_build_skill_rows_empty(tmp_path: Path):
    rows = build_skill_rows(scope="global", home=tmp_path, project=None)
    assert rows == []


def test_build_skill_rows_missing_canonical(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    import shutil
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    _add_demo_project(CliRunner(), git_sandbox.upstream, project)
    # Remove the canonical dir behind the lock's back.
    shutil.rmtree(project / ".agents" / "skills" / "demo")
    rows = build_skill_rows(scope="project", home=None, project=project)
    assert rows[0].state == "missing"
