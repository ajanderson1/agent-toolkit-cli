"""Exercise real catalog inventory and Textual pending/Apply behavior."""
import json

import pytest
from rich.text import Text

from agent_toolkit_tui.info_presentation import detail_sections, sections_markup
from tests.test_cli.test_reground import sandbox, git, invoke
from tests.test_cli.test_skill_catalog_acquire import subscribed


def _render_info_lines(lines) -> str:
    """Exercise the structured info renderer used by SkillGrid.action_info."""
    return Text.from_markup(sections_markup(detail_sections(lines)), emoji=False).plain


def test_catalog_rows_dedup_and_no_network_in_local_builder(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    from agent_toolkit_cli.skill_catalog import read_catalog
    from agent_toolkit_tui.skill_state import build_skill_rows
    snapshot = read_catalog()
    rows = build_skill_rows(scope="global", home=sandbox, project=None, catalog_snapshot=snapshot)
    assert len(rows) == 1 and rows[0].origin == "catalog"
    assert rows[0].state == "catalog" and rows[0].cells[("standard", "global")].available
    assert not (sandbox / ".agent-toolkit/skills-lock.json").exists()
    invoke("skills", "catalog", "add", "demo")
    rows = build_skill_rows(scope="global", home=sandbox, project=None, catalog_snapshot=snapshot)
    assert len(rows) == 1 and rows[0].origin == "library"


def test_info_shows_current_local_revision_before_any_upstream_check(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    invoke("skills", "catalog", "add", "demo")
    sha = git(sandbox / ".agent-toolkit/skills/demo", "rev-parse", "HEAD")
    from agent_toolkit_tui.asset_info import catalog_skill_info
    info = _render_info_lines(catalog_skill_info("demo", scope="global", home=sandbox, project=None))
    assert sha in info
    assert "not checked" in info.lower()
    assert not (sandbox / ".agent-toolkit/skills-update-checks.json").exists()


@pytest.mark.asyncio
async def test_successful_catalog_refresh_reports_configured_ref_and_fetched_revision(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path)
    git(cat, "tag", "catalog-release")
    invoke("catalog", "subscribe", cat.as_uri(), "--ref", "catalog-release")
    revision = git(cat, "rev-parse", "catalog-release")
    monkeypatch.chdir(tmp_path)
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    notifications = []
    original_notify = app.notify

    def spy_notify(message, *args, **kwargs):
        notifications.append((message, kwargs))
        return original_notify(message, *args, **kwargs)

    monkeypatch.setattr(app, "notify", spy_notify)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert (f"Retrieved catalogue catalog-release ({revision[:12]})", {}) in notifications


@pytest.mark.asyncio
async def test_successful_catalog_refresh_reports_fetched_revision_without_ref(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path)
    revision = git(cat, "rev-parse", "HEAD")
    monkeypatch.chdir(tmp_path)
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    notifications = []
    original_notify = app.notify

    def spy_notify(message, *args, **kwargs):
        notifications.append((message, kwargs))
        return original_notify(message, *args, **kwargs)

    monkeypatch.setattr(app, "notify", spy_notify)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert (f"Retrieved catalogue revision {revision[:12]}", {}) in notifications


@pytest.mark.asyncio
async def test_no_subscription_does_not_report_catalog_retrieval(sandbox, monkeypatch):
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    notifications = []
    original_notify = app.notify

    def spy_notify(message, *args, **kwargs):
        notifications.append((message, kwargs))
        return original_notify(message, *args, **kwargs)

    monkeypatch.setattr(app, "notify", spy_notify)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert all(not message.startswith("Retrieved catalogue") for message, _ in notifications)


@pytest.mark.asyncio
async def test_tui_pending_revert_apply_and_info(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path)
    monkeypatch.chdir(tmp_path)
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid
    from textual.widgets import Static
    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        assert grid.row_slugs == ["demo"]
        grid.cursor_to_cell(row_slug="demo", agent_name="standard")
        grid.action_toggle_cell()
        assert grid.pending_entries() == {("project", "standard", "demo"): "link"}
        assert not (sandbox / ".agent-toolkit/skills-lock.json").exists()
        app.action_revert()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert grid.pending_entries() == {}
        grid.cursor_to_cell(row_slug="demo", agent_name="standard")
        grid.action_toggle_cell()
        app._apply_skill_pending()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert (tmp_path / ".agents/skills/demo").is_symlink()
        assert not (tmp_path / ".agents/skills/other").exists()
        invoke("skills", "check", "demo", "-g")
        grid.cursor_to_cell(row_slug="demo", agent_name="standard")
        grid.action_info()
        await pilot.pause()
        body = str(app.screen.query_one("#cell-info-body", Static).render())
        assert "skills check" in body and "skills update" in body
        assert "checked" in body.lower() and "catalog" in body.lower()


@pytest.mark.asyncio
async def test_offline_refresh_hides_only_catalog_rows(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path)
    monkeypatch.chdir(tmp_path)
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid
    app = TUIApp()
    notifications = []
    original_notify = app.notify

    def spy_notify(message, *args, **kwargs):
        notifications.append((message, kwargs))
        return original_notify(message, *args, **kwargs)

    monkeypatch.setattr(app, "notify", spy_notify)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        assert "demo" in grid.row_slugs
        notifications.clear()
        cat.rename(tmp_path / "offline")
        app._refresh_skill_view()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert grid.row_slugs == []

    assert all(not message.startswith("Retrieved catalogue") for message, _ in notifications)
    assert any(kwargs.get("severity") == "warning" for _, kwargs in notifications)


@pytest.mark.asyncio
async def test_catalog_source_change_after_toggle_refuses_apply(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path)
    monkeypatch.chdir(tmp_path)
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid
    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        grid.cursor_to_cell(row_slug="demo", agent_name="standard")
        grid.action_toggle_cell()
        data = json.loads((cat / "catalog.json").read_text())
        data["skills"][0]["path"] = "skills/other"
        (cat / "catalog.json").write_text(json.dumps(data))
        git(cat, "add", ".")
        git(cat, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "changed")
        result = app._apply_skill_pending()
        assert result.failed and any("changed" in e for e in result.errors)
        assert not (sandbox / ".agents/skills/demo").exists()
        assert not (sandbox / ".agent-toolkit/skills-lock.json").exists()
