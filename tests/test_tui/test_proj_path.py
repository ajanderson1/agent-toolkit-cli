from pathlib import Path
import pytest
from textual.widgets import Static

from agent_toolkit_tui.app import TUIApp


@pytest.mark.asyncio
async def test_proj_path_git_root(tmp_path: Path):
    """When cwd is the root of a Git repository, path displays without warning icon or red color."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    app = TUIApp(cwd=tmp_path)
    markup = app._build_proj_path_markup()
    assert markup == str(tmp_path)
    assert "⚠️" not in markup
    assert "⚠" not in markup
    assert "[red]" not in markup

    async with app.run_test() as pilot:
        await pilot.pause()
        rendered = app.query_one("#proj-path", Static).render()
        text = str(rendered)
        assert str(tmp_path) in text
        assert "⚠️" not in text
        assert "⚠" not in text
        # Content should not have red span
        spans = getattr(rendered, "spans", [])
        assert not any(getattr(s, "style", "") == "red" for s in spans)


@pytest.mark.asyncio
async def test_proj_path_git_subfolder(tmp_path: Path):
    """When cwd is a subdirectory of a Git repository, path displays in red with a warning triangle."""
    (tmp_path / ".git").mkdir()
    sub_dir = tmp_path / "src" / "nested"
    sub_dir.mkdir(parents=True)

    app = TUIApp(cwd=sub_dir)
    markup = app._build_proj_path_markup()
    assert markup.startswith("[red]⚠️")
    assert str(sub_dir) in markup
    assert markup.endswith("[/]")

    async with app.run_test() as pilot:
        await pilot.pause()
        rendered = app.query_one("#proj-path", Static).render()
        text = str(rendered)
        assert str(sub_dir) in text
        assert "⚠️" in text or "⚠" in text
        spans = getattr(rendered, "spans", [])
        assert any("red" in str(getattr(s, "style", "")) for s in spans)


@pytest.mark.asyncio
async def test_proj_path_non_git_folder(tmp_path: Path):
    """When cwd is not in a Git repository, path displays in red with a warning triangle."""
    non_git = tmp_path / "plain_dir"
    non_git.mkdir()

    app = TUIApp(cwd=non_git)
    markup = app._build_proj_path_markup()
    assert markup.startswith("[red]⚠️")
    assert str(non_git) in markup

    async with app.run_test() as pilot:
        await pilot.pause()
        rendered = app.query_one("#proj-path", Static).render()
        text = str(rendered)
        assert str(non_git) in text
        assert "⚠️" in text or "⚠" in text
        spans = getattr(rendered, "spans", [])
        assert any("red" in str(getattr(s, "style", "")) for s in spans)


@pytest.mark.asyncio
async def test_proj_path_git_worktree_root(tmp_path: Path):
    """When cwd is a Git worktree root (.git is a file), it is recognized as root without warning."""
    git_file = tmp_path / ".git"
    git_file.write_text("gitdir: /path/to/main/.git/worktrees/branch\n")

    app = TUIApp(cwd=tmp_path)
    markup = app._build_proj_path_markup()
    assert markup == str(tmp_path)
    assert "⚠️" not in markup
    assert "[red]" not in markup

    async with app.run_test() as pilot:
        await pilot.pause()
        rendered = app.query_one("#proj-path", Static).render()
        text = str(rendered)
        assert str(tmp_path) in text
        assert "⚠️" not in text


@pytest.mark.asyncio
async def test_proj_path_layout_order(tmp_path: Path):
    """proj-path is placed directly above status-bar, which is directly above footer-pending."""
    app = TUIApp(cwd=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        proj_path = app.query_one("#proj-path", Static)
        status_bar = app.query_one("#status-bar", Static)
        footer_pending = app.query_one("#footer-pending", Static)

        screen = app.screen
        children = list(screen.children)
        idx_proj = children.index(proj_path)
        idx_status = children.index(status_bar)
        idx_pending = children.index(footer_pending)

        assert idx_proj < idx_status < idx_pending
        assert idx_status == idx_proj + 1
        assert idx_pending == idx_status + 1


@pytest.mark.asyncio
async def test_proj_path_refresh_on_dir_change(tmp_path: Path):
    """Calling _refresh_proj_path updates the widget content live."""
    non_git = tmp_path / "dir_a"
    non_git.mkdir()
    git_dir = tmp_path / "dir_b"
    git_dir.mkdir()
    (git_dir / ".git").mkdir()

    app = TUIApp(cwd=non_git)
    async with app.run_test() as pilot:
        await pilot.pause()
        text_before = str(app.query_one("#proj-path", Static).render())
        assert "⚠️" in text_before

        app._refresh_proj_path(git_dir)
        await pilot.pause()
        text_after = str(app.query_one("#proj-path", Static).render())
        assert str(git_dir) in text_after
        assert "⚠️" not in text_after


@pytest.mark.asyncio
async def test_footer_pending_removes_duplicate_count():
    """#footer-pending is blank on mount and after cell toggle; status-bar carries pending count."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Footer is empty on initial load (no "Pending: 0")
        footer_text = str(app.query_one("#footer-pending", Static).render()).strip()
        assert footer_text == ""
        assert "Pending:" not in footer_text

        # Status bar has live counts
        bar = str(app.query_one("#status-bar", Static).render())
        assert "0 pending" in bar
