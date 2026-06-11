"""#360 AC2: TUI Apply fully uninstalls an unlisted row — projections detached
AND project lock entry dropped (non-destructive: canonical preserved)."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, lock_file_path
from agent_toolkit_tui.app import TUIApp


@pytest.mark.asyncio
async def test_apply_full_uninstall_unlisted_drops_project_entry(
    git_sandbox, tmp_path: Path, monkeypatch,
):
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

    # The TUI apply path resolves the project as Path.cwd().
    monkeypatch.chdir(project)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
        grid = app.query_one("#skill-grid", SkillGrid)
        # Queue an unlink for every linked, non-skipped cell of the demo row
        # at project scope (full uninstall), then apply.
        pending = {}
        for row in grid._rows:  # SkillGrid stores rows in `_rows` (skill_grid.py:113)
            if row.slug != "demo":
                continue
            for (agent, scope), cell in row.cells.items():
                if scope == "project" and cell.linked and not cell.skipped:
                    pending[(scope, agent, "demo")] = "unlink"
        assert pending, "expected at least one linked project cell to unlink"
        grid.restore_pending(pending)
        app._apply_skill_pending()
        await pilot.pause()

    proj_lock = read_lock(lock_file_path(scope="project", project=project))
    assert "demo" not in proj_lock.skills          # entry dropped
    canonical = canonical_skill_dir("demo", scope="project", project=project)
    assert canonical.exists()                      # non-destructive: canonical preserved
    # The apply genuinely detached projections (it consulted the pending ops,
    # not the library — spec D4): the claude-code projection symlink is gone.
    from agent_toolkit_cli.skill_paths import agent_projection_dir
    link = agent_projection_dir("claude-code", "demo", scope="project", home=None, project=project)
    assert not link.is_symlink()


@pytest.mark.asyncio
async def test_apply_failure_keeps_project_entry(git_sandbox, tmp_path: Path, monkeypatch):
    """#360 AC2 failure path: if the engine apply errors, the project lock
    entry is NOT dropped (the drop only follows a successful apply)."""
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
    monkeypatch.chdir(project)

    # Patch the SOURCE module (app.py imports inside the method, so the
    # call resolves through skill_install at apply time — same monkeypatch
    # trap as #337's doctor_cmd lesson).
    import agent_toolkit_cli.skill_install as skill_install

    def _boom(*args, **kwargs):
        raise skill_install.InstallError("boom")

    monkeypatch.setattr(skill_install, "apply", _boom)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets.skill_grid import SkillGrid
        grid = app.query_one("#skill-grid", SkillGrid)
        grid.restore_pending({("project", "claude-code", "demo"): "unlink"})
        app._apply_skill_pending()
        await pilot.pause()

    proj_lock = read_lock(lock_file_path(scope="project", project=project))
    assert "demo" in proj_lock.skills  # entry survives a failed apply
