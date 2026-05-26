import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_paths import canonical_skill_dir


def _add_and_install_project(runner, upstream_path, project):
    """Add to library then install at project scope."""
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


def _advance_upstream(git_sandbox, files: dict[str, str]):
    import shutil
    other = git_sandbox.upstream.parent / "advancer"
    if other.exists():
        shutil.rmtree(other)
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    for name, content in files.items():
        (other / name).write_text(content)
        subprocess.run(
            ["git", "-C", str(other), "add", name],
            check=True, env=git_sandbox.env, capture_output=True,
        )
    subprocess.run(
        ["git", "-C", str(other), "commit", "-m", "advance"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(other), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )


def test_update_fast_forwards_clean(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    assert _add_and_install_project(runner, git_sandbox.upstream, project).exit_code == 0
    _advance_upstream(git_sandbox, {"NEW.md": "from upstream\n"})
    result = runner.invoke(main, [
        "--project", str(project), "skill", "update", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert (canonical_skill_dir("demo", scope="project", project=project) / "NEW.md").exists()


def test_update_no_flag_outside_project_uses_global(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """No flag + no project lock at cwd → update consults global lock (#220).

    Mirrors the #216 list/status fix for verbs that mutate.
    """
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
        "--project", str(not_a_project), "skill", "update", "demo",
    ])
    assert result.exit_code == 0, result.output
    assert "not in lock" not in result.output
    assert "demo" in result.output  # at least a slug-bearing status line


def test_update_surfaces_conflict_and_exits_nonzero(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    assert _add_and_install_project(runner, git_sandbox.upstream, project).exit_code == 0

    canonical = canonical_skill_dir("demo", scope="project", project=project)
    (canonical / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Local edit.\n---\n# demo local\n"
    )
    subprocess.run(
        ["git", "-C", str(canonical), "add", "SKILL.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(canonical), "commit", "-m", "local"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    _advance_upstream(git_sandbox, {
        "SKILL.md":
            "---\nname: demo\ndescription: Upstream edit.\n---\n# demo upstream\n"
    })
    result = runner.invoke(main, [
        "--project", str(project), "skill", "update", "demo", "-p",
    ])
    assert result.exit_code != 0
    assert "conflict" in result.output.lower()
    assert "<<<<<<<" in (canonical / "SKILL.md").read_text()


# ---------------------------------------------------------------------------
# Task 6 — E2E characterization: update across git states (global scope)
# Covers Gap Ledger §2 (no "already up to date") and §3 (terse conflict).
# ---------------------------------------------------------------------------


def _setup_global_demo(git_sandbox, tmp_path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                             "--slug", "demo"])
    assert r.exit_code == 0, r.output
    return runner, library_root


def test_update_behind_fast_forwards(git_sandbox, tmp_path, monkeypatch):
    runner, root = _setup_global_demo(git_sandbox, tmp_path, monkeypatch)
    _advance_upstream(git_sandbox, {"UPSTREAM.md": "upstream\n"})
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert "updated" in result.output
    assert (root / "demo" / "UPSTREAM.md").exists()


def test_update_up_to_date_still_says_updated(git_sandbox, tmp_path, monkeypatch):
    """Documents current behaviour: update prints 'updated' even when already
    current — no 'already up to date'. See Gap Ledger §2."""
    runner, root = _setup_global_demo(git_sandbox, tmp_path, monkeypatch)
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert "updated" in result.output


def test_update_conflict_exits_nonzero_and_is_terse(git_sandbox, tmp_path, monkeypatch):
    """Documents current behaviour: conflict → exit 1 + git-literate message,
    no copy-paste resolver. See Gap Ledger §3."""
    runner, root = _setup_global_demo(git_sandbox, tmp_path, monkeypatch)
    # Local edit in canonical, conflicting upstream edit on the same file.
    (root / "demo" / "SKILL.md").write_text("local edit\n")
    subprocess.run(["git", "-C", str(root / "demo"), "commit", "-am", "local"],
                   check=True, env=git_sandbox.env, capture_output=True)
    _advance_upstream(git_sandbox, {"SKILL.md": "upstream edit\n"})
    result = runner.invoke(main, ["skill", "update", "demo", "-g"])
    assert result.exit_code == 1
    assert "conflict" in result.output.lower()
    assert "claude" not in result.output.lower()  # no resolver yet — the gap
    assert "<<<<<<<" in (root / "demo" / "SKILL.md").read_text()


def test_update_copymode_refuses(copymode_skill):
    """copy-mode (no .git/) → refuse with re-add guidance, exit 1."""
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "update", "copydemo", "-g"])
    assert result.exit_code == 1
    assert "copy-mode" in result.output
