from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_paths import canonical_skill_dir
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

    canonical = canonical_skill_dir("demo", scope="project", project=project)
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


def test_skill_status_no_flag_outside_project_uses_global(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """No flag + no project lock at cwd → consult global lock (#210)."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output

    not_a_project = tmp_path / "not-a-project"
    not_a_project.mkdir()
    result = runner.invoke(main, [
        "--project", str(not_a_project), "skill", "status", "demo",
    ])
    assert result.exit_code == 0, result.output
    assert "demo" in result.output
    assert "(not in lock)" not in result.output


def test_skill_status_project_flag_outside_project_shows_hint(
    tmp_path: Path, monkeypatch,
):
    """`-p` forced + no project lock → clear hint (#210)."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    not_a_project = tmp_path / "not-a-project"
    not_a_project.mkdir()

    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(not_a_project), "skill", "status", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert "no project skills here" in result.output


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
