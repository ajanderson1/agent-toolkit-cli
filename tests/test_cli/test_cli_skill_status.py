from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_skill_update_monorepo import _init_parent


def _add_and_install_project(runner, upstream_path, project, library_root):
    """Add to library then install at project scope with claude-code."""
    r = runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo",
    ])
    if r.exit_code != 0:
        return r
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])


def test_skill_status_clean(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_and_install_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "--project", str(project), "skill", "status", "-p",
    ])
    assert result.exit_code == 0
    assert "demo" in result.output
    assert "clean" in result.output


def test_skill_status_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_and_install_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output

    canonical = project / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text("self-edit\n")
    result = runner.invoke(main, [
        "--project", str(project), "skill", "status", "-p",
    ])
    assert result.exit_code == 0
    assert "dirty" in result.output


def test_skill_status_monorepo_clean(tmp_path: Path, monkeypatch):
    """Fresh monorepo install — parent clone is clean → status reports clean."""
    parent = _init_parent(tmp_path)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r = runner.invoke(
        main, ["skill", "add", f"file://{parent}", "--skill", "mkdocs"]
    )
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, ["skill", "status", "-g"])
    assert result.exit_code == 0, result.output
    assert "mkdocs" in result.output
    assert "clean" in result.output
    assert "copy" not in result.output


def test_skill_status_monorepo_dirty(tmp_path: Path, monkeypatch):
    """Uncommitted edit in the parent clone → status reports dirty."""
    parent = _init_parent(tmp_path)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r = runner.invoke(
        main, ["skill", "add", f"file://{parent}", "--skill", "mkdocs"]
    )
    assert r.exit_code == 0, r.output

    candidates = list((library / "skills" / "_parents").glob("*/*"))
    assert len(candidates) == 1, candidates
    parent_clone = candidates[0]
    (parent_clone / "mkdocs" / "SKILL.md").write_text("dirty\n")

    result = runner.invoke(main, ["skill", "status", "-g"])
    assert result.exit_code == 0, result.output
    assert "mkdocs" in result.output
    assert "dirty" in result.output
