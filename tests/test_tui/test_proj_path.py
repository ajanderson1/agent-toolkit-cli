from pathlib import Path

import pytest
from rich.console import Console
from rich.text import Text
from textual.widgets import Static

from agent_toolkit_tui.app import TUIApp


def assert_path_styles(rendered: Text, path: Path, *, warning: bool) -> None:
    prefix = "⚠️  " if warning else ""
    assert rendered.plain == f"{prefix}REPO:{path}"
    console = Console()
    path_start = len(prefix) + len("REPO:")
    final_start = len(rendered.plain) - len(path.name or str(path))
    offset = 0
    for segment in console.render(rendered, console.options.update(width=1000)):
        for char in segment.text:
            if offset >= len(rendered.plain):
                break
            assert char == rendered.plain[offset]
            style = segment.style
            expected_bold = len(prefix) <= offset < path_start or offset >= final_start
            assert bool(style and style.bold) == expected_bold, (offset, style)
            is_red = bool(style and style.color and style.color.get_truecolor() in {(128, 0, 0), (255, 0, 0)})
            assert is_red == warning, (offset, style)
            offset += 1
    assert offset == len(rendered.plain)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["git-root", "subdirectory", "non-git", "worktree"])
@pytest.mark.parametrize("names", [("parent", "slug"), ("parent [red] space", "slug [bold] space")])
async def test_proj_path_rendered_styles(tmp_path: Path, kind: str, names: tuple[str, str]):
    parent = tmp_path / names[0]
    path = parent / names[1]
    path.mkdir(parents=True)
    if kind == "git-root":
        (path / ".git").mkdir()
    elif kind == "subdirectory":
        (parent / ".git").mkdir()
    elif kind == "worktree":
        (path / ".git").write_text("gitdir: /path/to/main/.git/worktrees/branch\n")
    warning = kind in {"subdirectory", "non-git"}
    app = TUIApp(cwd=path)
    assert_path_styles(Text.from_markup(app._build_proj_path_markup()), path, warning=warning)

    async with app.run_test(size=(160, 30)) as pilot:
        await pilot.pause()
        assert_path_styles(app.query_one("#proj-path", Static).render(), path, warning=warning)


def test_proj_path_filesystem_root(monkeypatch):
    root = Path(Path.cwd().anchor)
    monkeypatch.setattr("agent_toolkit_cli.skill_git.is_git_repo", lambda cwd: False)
    app = TUIApp(cwd=root)
    assert_path_styles(Text.from_markup(app._build_proj_path_markup()), root, warning=True)


@pytest.mark.asyncio
async def test_proj_path_layout_order(tmp_path: Path):
    app = TUIApp(cwd=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        proj_path = app.query_one("#proj-path", Static)
        status_bar = app.query_one("#status-bar", Static)
        footer_pending = app.query_one("#footer-pending", Static)
        footer_status = app.query_one("#footer-status")
        catalog_status = app.query_one("#catalog-status", Static)
        children = list(app.screen.children)
        assert children.index(status_bar) == children.index(proj_path) + 1
        assert children.index(footer_status) == children.index(status_bar) + 1
        assert list(footer_status.children) == [footer_pending, catalog_status]
        assert footer_pending.region.y == catalog_status.region.y


@pytest.mark.asyncio
async def test_proj_path_refresh_on_dir_change(tmp_path: Path):
    non_git = tmp_path / "dir_a"
    non_git.mkdir()
    git_dir = tmp_path / "dir_b"
    git_dir.mkdir()
    (git_dir / ".git").mkdir()

    app = TUIApp(cwd=non_git)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert_path_styles(app.query_one("#proj-path", Static).render(), non_git, warning=True)
        app._refresh_proj_path(git_dir)
        await pilot.pause()
        assert_path_styles(app.query_one("#proj-path", Static).render(), git_dir, warning=False)
        app._refresh_proj_path()
        await pilot.pause()
        assert_path_styles(app.query_one("#proj-path", Static).render(), non_git, warning=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [50, 160])
async def test_proj_path_visual_evidence(tmp_path: Path, monkeypatch, width: int):
    artifacts = Path("assets/verification/527").resolve()
    monkeypatch.chdir(tmp_path)
    path = Path("parent [red] space") / "final [bold] dir"
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    artifacts.mkdir(parents=True, exist_ok=True)
    app = TUIApp(cwd=path)
    async with app.run_test(size=(width, 30)) as pilot:
        await pilot.pause()
        bar = app.query_one("#proj-path", Static)
        assert_path_styles(bar.render(), path, warning=False)
        assert bar.region.bottom <= app.query_one("#status-bar").region.y
        assert bar.size.height == 1
        (artifacts / f"path-{width}.svg").write_text(app.export_screenshot(), encoding="utf-8")
        (path / ".git").rmdir()
        app._refresh_proj_path()
        await pilot.pause()
        assert_path_styles(bar.render(), path, warning=True)
        (artifacts / f"warning-{width}.svg").write_text(app.export_screenshot(), encoding="utf-8")


@pytest.mark.asyncio
async def test_footer_pending_removes_duplicate_count():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        footer_text = str(app.query_one("#footer-pending", Static).render()).strip()
        assert footer_text == ""
        assert "Pending:" not in footer_text
        bar = str(app.query_one("#status-bar", Static).render())
        assert "0 pending" in bar
