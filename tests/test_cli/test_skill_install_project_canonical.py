"""#360: ensure_project_canonical must not require a library entry when the
project install is already complete (canonical + project lock entry)."""
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_install import ensure_project_canonical
from agent_toolkit_cli.skill_paths import library_lock_path


def test_ensure_project_canonical_unlisted_is_noop(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    # Must NOT raise "not in global library": install is already complete.
    p = ensure_project_canonical(
        slug="demo", project=project, global_lock_path=library_lock_path(),
    )
    assert p.exists()
