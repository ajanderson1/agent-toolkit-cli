"""Disposable regressions for consequential whole-branch review findings."""

import json

import pytest

from pathlib import Path
from agent_toolkit_cli.skill_install import InstallError
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_reground import sandbox, repo, git, invoke
from tests.test_cli.test_skill_catalog import catalog_repo


@pytest.mark.asyncio
async def test_flat_root_and_new_nested_child_cannot_partially_apply(
    tmp_path, sandbox, monkeypatch
):
    source_base = tmp_path / "upstream"
    source_base.mkdir()
    upstream = repo(
        source_base, {"SKILL.md": "---\nname: root\ndescription: root\n---\n"}
    )
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("skills", "add", upstream.as_uri(), "--slug", "root-skill", "--ref", "main")
    invoke(
        "skills", "install", "root-skill", "--scope", "project", "--agents", "standard"
    )
    nested = upstream / "skills/nested/SKILL.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("---\nname: nested\ndescription: nested\n---\n")
    git(upstream, "add", ".")
    git(
        upstream,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "commit",
        "-m",
        "nested child",
    )
    cat_base = tmp_path / "catalog"
    cat_base.mkdir()
    cat = catalog_repo(
        cat_base,
        {
            "version": 1,
            "skills": [
                dict(
                    key=key,
                    description=key,
                    source=upstream.as_uri(),
                    path=path,
                    ref="main",
                )
                for key, path in [("root-skill", "."), ("nested", "skills/nested")]
            ],
        },
    )
    invoke("skills", "catalog", "subscribe", cat.as_uri())
    root_canonical = sandbox / ".agent-toolkit/skills/root-skill"
    original_head = git(root_canonical, "rev-parse", "HEAD")
    original = Path.unlink
    failures = []

    def fail_root(path, *args, **kwargs):
        if path == project / ".agents/skills/root-skill":
            assert (project / ".agents/skills/nested").exists()
            failures.append(path)
            raise InstallError("injected root unlink failure")
        return original(path, *args, **kwargs)

    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        for slug in ("root-skill", "nested"):
            grid.cursor_to_cell(row_slug=slug, agent_name="standard")
            grid.action_toggle_cell()
        assert len(grid.pending_entries()) == 2
        monkeypatch.setattr(Path, "unlink", fail_root)
        result = app._apply_skill_pending()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert result.failed
        assert (project / ".agents/skills/root-skill").exists()
        assert not (project / ".agents/skills/nested").exists(), result.errors
        assert result.failed == 2
        assert len(grid.pending_entries()) == 2
        assert len(failures) == 1
        monkeypatch.setattr(Path, "unlink", original)
        result = app._apply_skill_pending()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert not result.failed, result.errors
        assert not (project / ".agents/skills/root-skill").exists()
        assert (project / ".agents/skills/nested").exists()
        assert (
            root_canonical.is_dir()
            and git(root_canonical, "rev-parse", "HEAD") == original_head
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("initially_enabled", [False, True])
async def test_materialised_singleton_keeps_ordinary_enable_disable(
    tmp_path, sandbox, monkeypatch, initially_enabled
):
    upstream = repo(
        tmp_path, {"skills/demo/SKILL.md": "---\nname: demo\ndescription: demo\n---\n"}
    )
    with monkeypatch.context() as no_symlinks:

        def refuse(*args, **kwargs):
            raise OSError("symlink unavailable during acquisition")

        no_symlinks.setattr(Path, "symlink_to", refuse)
        invoke(
            "skills", "add", upstream.as_uri(), "--path", "skills/demo", "--ref", "main"
        )
    library = sandbox / ".agent-toolkit/skills/demo"
    assert library.is_dir() and not library.is_symlink()
    record = json.loads((sandbox / ".agent-toolkit/skills-lock.json").read_text())[
        "skills"
    ]["demo"]
    assert record["materialised"] == "copy"
    (library / "local.txt").write_text("retain exactly")
    if initially_enabled:
        invoke("skills", "install", "demo", "--scope", "global", "--agents", "standard")
    app = TUIApp()
    app._scope = "global"
    monkeypatch.chdir(tmp_path)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        grid.cursor_to_cell(row_slug="demo", agent_name="standard")
        grid.action_toggle_cell()
        assert len(grid.pending_entries()) == 1
        result = app._apply_skill_pending()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert not result.failed, result.errors
        assert (sandbox / ".agents/skills/demo").exists() == (not initially_enabled)
        assert (library / "local.txt").read_text() == "retain exactly"
        assert not grid.pending_entries()
