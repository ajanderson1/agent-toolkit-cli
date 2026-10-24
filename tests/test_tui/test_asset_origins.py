"""#538: origin copy and controls must not claim discovered local assets."""
from pathlib import Path
import shlex

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import AgentCell, AgentRow, build_agent_rows
from agent_toolkit_tui.skill_state import SkillCell, SkillRow, build_skill_rows
from agent_toolkit_tui.widgets.agent_grid import AgentGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow, build_pi_rows
from agent_toolkit_tui.widgets.pi_grid import PiGrid


class GridApp(App):
    def __init__(self, grid):
        super().__init__()
        self.grid = grid

    def compose(self) -> ComposeResult:
        yield self.grid


def make_grid(kind, scope, path, *, local_linked=True, library_linked=False):
    if kind == "skill":
        return SkillGrid([
            SkillRow("a-local", str(path), "(untracked)", "unlisted",
                     {("standard", scope): SkillCell(local_linked, False, False)}),
            SkillRow("b-library", "owner/repo", "main", "dirty",
                     {("standard", scope): SkillCell(library_linked, False, False)}),
        ])
    return AgentGrid([
        AgentRow("a-local", str(path), "(untracked)", "unlisted",
                 {("standard", scope): AgentCell(local_linked)}),
        AgentRow("b-library", "owner/repo", "main", "unlisted",
                 {("standard", scope): AgentCell(library_linked)}),
    ])


@pytest.mark.parametrize("kind", ["skill", "agent"])
@pytest.mark.parametrize("scope", ["global", "project"])
@pytest.mark.parametrize("local_linked", [False, True])
@pytest.mark.asyncio
async def test_local_never_enters_single_or_bulk_queues(kind, scope, local_linked, tmp_path):
    grid = make_grid(kind, scope, tmp_path / "local", local_linked=local_linked)
    grid.set_scope(scope)
    async with GridApp(grid).run_test() as pilot:
        table = grid.query_one(DataTable)
        table.cursor_coordinate = Coordinate(0, 1)
        grid.action_toggle_cell()
        assert grid.pending_entries() == {}
        grid.action_toggle_column()
        assert grid.pending_entries() == {(scope, "standard", "b-library"): "link"}
        grid.action_toggle_column()
        assert grid.pending_entries() == {}
        # Now all controlled rows are on: None must ignore a local off-cell too.
        grid.set_rows(make_grid(kind, scope, tmp_path / "local", local_linked=local_linked,
                                library_linked=True)._rows)
        table.cursor_coordinate = Coordinate(0, 1)
        grid.action_toggle_column()
        assert grid.pending_entries() == {(scope, "standard", "b-library"): "unlink"}
        await pilot.pause()


@pytest.mark.parametrize("kind", ["skill", "agent"])
@pytest.mark.parametrize("shape", ["file", "directory", "symlink"])
@pytest.mark.asyncio
async def test_local_info_explains_exact_manual_removal(kind, shape, tmp_path):
    parent = tmp_path / "shared checkout"
    parent.mkdir()
    path = parent / "one [red]"
    if shape == "symlink":
        target = tmp_path / "preserved target"
        target.mkdir()
        path.symlink_to(target, target_is_directory=True)
    elif shape == "directory":
        path.mkdir()
    else:
        path.write_text("local content")
    grid = make_grid(kind, "global", path)
    async with GridApp(grid).run_test() as pilot:
        grid.query_one(DataTable).cursor_coordinate = Coordinate(0, 0)
        grid.action_info()
        await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        assert "Origin: local" in body
        assert str(path) in body
        assert f"Source: {path}" in body
        assert "unlisted" not in body
        assert "not moved or registered" in body
        assert "Edit/update these files directly" in body
        command = next(line.strip() for line in body.splitlines() if line.strip().startswith("rm "))
        args = shlex.split(command)
        assert args[-1] == str(path)
        assert str(parent) not in args
        if shape == "symlink":
            assert args == ["rm", "--", str(path)]
            assert "target files are kept" in body
        else:
            assert "permanently deletes" in body
        assert "adopt" not in body.lower()


@pytest.mark.parametrize("kind", ["skill", "agent"])
@pytest.mark.parametrize("source", ["owner/repo", "/registered/local/git/repo"])
@pytest.mark.asyncio
async def test_library_info_preserves_control_and_health(kind, source, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    grid = make_grid(kind, "global", tmp_path / "local")
    grid._rows[1].source = source
    async with GridApp(grid).run_test() as pilot:
        table = grid.query_one(DataTable)
        table.cursor_coordinate = Coordinate(1, 1)
        grid.action_toggle_cell()
        assert grid.pending_entries() == {("global", "standard", "b-library"): "link"}
        grid.action_info()
        await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        assert "Origin: library" in body
        assert "Disable removes the connection, not the source" in body
        assert "Source path:" in body
        if kind == "skill":
            assert "dirty" in body


@pytest.mark.parametrize("scope", ["global", "project"])
@pytest.mark.asyncio
async def test_collection_toggle_excludes_local_members(scope, tmp_path):
    grid = make_grid("skill", scope, tmp_path / "local")
    for row in grid._rows:
        row.collection_key = ("owner/repo", "main")
        row.collection_label = "repo"
    grid.set_scope(scope)
    async with GridApp(grid).run_test() as pilot:
        grid.query_one(DataTable).cursor_coordinate = Coordinate(0, 1)
        grid.action_toggle_cell()
        assert grid.pending_entries() == {(scope, "standard", "b-library"): "link"}
        await pilot.pause()


@pytest.mark.asyncio
async def test_long_local_info_can_scroll_to_removal_guidance(tmp_path):
    path = tmp_path / ("long checkout " * 10) / "child"
    grid = make_grid("skill", "global", path)
    async with GridApp(grid).run_test(size=(60, 18)) as pilot:
        grid.action_info()
        await pilot.pause()
        screen = grid.app.screen
        panel = screen.children[0]
        assert panel.region.bottom <= screen.size.height
        assert panel.region.right <= screen.size.width
        assert panel.max_scroll_y > 0
        panel.scroll_end(animate=False, force=True)
        await pilot.pause()
        footer = screen.query_one("#cell-info-footer")
        assert 0 <= footer.region.y < screen.size.height
        assert footer.region.bottom <= screen.size.height


@pytest.mark.parametrize("origin,managed,label", [
    ("store-owned", True, "library"), ("npm", True, "npm"),
    ("npm", False, "npm"), ("untracked", False, "local"),
    ("local-package", False, "local"),
])
@pytest.mark.asyncio
async def test_pi_origin_labels_and_active_info(origin, managed, label, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    settings = tmp_path / ".pi/agent/settings.json"
    settings.parent.mkdir(parents=True)
    spec = "npm:@scope/pkg" if origin == "npm" else "../local package"
    cell = PiCell(True, False, origin, managed=managed)
    row = PiExtensionRow("demo", origin, spec, cell, cell, managed=managed,
                         global_config_path=str(settings), global_package_spec=spec)
    if origin == "npm":
        from tests.pi_npm_fixtures import display_state
        row.npm_state = display_state("@scope/pkg", True, False)
    if origin == "untracked":
        loose = tmp_path / ".pi/agent/extensions/demo.ts"
        loose.parent.mkdir()
        loose.write_text("export default () => {}")
    grid = PiGrid([row])
    async with GridApp(grid).run_test() as pilot:
        assert Text.from_markup(str(grid.query_one(DataTable).get_cell_at(Coordinate(0, 2)))).plain == label
        grid.action_info()
        await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        if origin in ("store-owned", "untracked"):
            assert f"Origin: {label}" in body
        assert "adopt" not in body.lower()
        if origin == "npm":
            assert "download status is not checked" not in body
            assert "Enabled globally: Enabled" in body
            assert "Enabled for this project: Disabled" in body
            assert "Remove installation/declaration: agent-toolkit-cli pi-extensions remove npm:@scope/pkg --global" in body
            assert "files and declarations are retained" in body
            assert "did not register" not in body
            assert "second unregister step" in body
        elif origin == "local-package":
            assert str(settings) in body
            assert str(settings.parent / "../local package") in body
            assert spec in body
            assert "packages" in body
            assert "does not delete" in body
        elif origin == "untracked":
            assert str(loose) in body
            assert "permanently deletes" in body
        else:
            assert "Source path:" in body
            assert "Disable removes the connection, not the source" in body


@pytest.mark.parametrize("scope", ["global", "project"])
@pytest.mark.parametrize("shape", ["file", "symlink", "directory"])
@pytest.mark.asyncio
async def test_pi_loose_info_uses_exact_scoped_path(scope, shape, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    root = tmp_path / ".pi/agent/extensions" if scope == "global" else project / ".pi/extensions"
    root.mkdir(parents=True)
    path = root / ("loose.js" if shape != "directory" else "loose")
    if shape == "directory":
        path.mkdir()
        (path / "index.ts").write_text("export default () => {}")
    elif shape == "symlink":
        target = tmp_path / "target.js"
        target.write_text("export default () => {}")
        path.symlink_to(target)
    else:
        path.write_text("export default () => {}")
    grid = PiGrid(build_pi_rows(home=tmp_path, project=project))
    grid.set_scope(scope)
    async with GridApp(grid).run_test() as pilot:
        grid.action_toggle_cell()
        assert grid.pending_entries() == {}
        grid.action_info()
        await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        assert str(path) in body
        command = next(line.strip() for line in body.splitlines() if line.strip().startswith("rm "))
        assert shlex.split(command)[-1] == str(path)
        if shape == "symlink":
            assert shlex.split(command) == ["rm", "--", str(path)]
            assert "target files are kept" in body


@pytest.mark.asyncio
async def test_collection_info_uses_real_child_backing_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "library"))
    target = tmp_path / "checkout/skills/one"
    target.mkdir(parents=True)
    link = tmp_path / "library/one"
    link.parent.mkdir()
    link.symlink_to(target)
    row = SkillRow("one", "owner/repo", "main", "clean",
                   collection_key=("owner/repo", "main"), collection_label="repo",
                   skill_path="skills/one")
    grid = SkillGrid([row])
    async with GridApp(grid).run_test() as pilot:
        grid.query_one(DataTable).cursor_coordinate = Coordinate(0, 0)
        grid.action_info()
        await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        assert f"Source path: {tmp_path / 'checkout'}" in body


@pytest.mark.parametrize("kind", ["skill", "agent"])
@pytest.mark.asyncio
async def test_library_source_path_resolves_symlink(kind, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / ".agent-toolkit/skills"))
    root = tmp_path / f".agent-toolkit/{'skills' if kind == 'skill' else 'agents'}"
    root.mkdir(parents=True)
    target = tmp_path / "checkout/actual child"
    target.mkdir(parents=True)
    (root / "b-library").symlink_to(target)
    grid = make_grid(kind, "global", tmp_path / "local")
    async with GridApp(grid).run_test() as pilot:
        grid.query_one(DataTable).cursor_coordinate = Coordinate(1, 0)
        grid.action_info()
        await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        assert f"Source path: {target}" in body


def test_discovered_skill_child_retains_actual_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    root = tmp_path / ".agent-toolkit/skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(root))
    child = root / "bundle/skills/one"
    child.mkdir(parents=True)
    (child / "SKILL.md").write_text("---\ndescription: local\n---\n")
    row = next(r for r in build_skill_rows(scope="global", home=tmp_path, project=None)
               if r.slug == "bundle:one")
    assert row.source == str(child)


def test_discovered_agent_retains_actual_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / ".claude/agents/local.md"
    path.parent.mkdir(parents=True)
    path.write_text("local agent")
    row = next(r for r in build_agent_rows(scope="global", home=tmp_path, project=None)
               if r.slug == "local")
    assert row.source == str(path)
