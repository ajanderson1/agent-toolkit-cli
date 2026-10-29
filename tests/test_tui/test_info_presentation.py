"""Structured hierarchy shared by asset and column info panes (#555)."""
from __future__ import annotations

from pathlib import Path

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Static

from agent_toolkit_tui.asset_info import local_path_info
from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.screens.cell_info import CellInfoScreen, asset_info_body
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal


def test_asset_info_leads_with_glance_facts_and_omits_empty_description() -> None:
    body = asset_info_body(
        asset_label="Skill",
        slug="journal",
        description=None,
        description_location="SKILL.md",
        source="example/journal",
        origin="library",
        ref="main",
        state="clean",
        scope="global",
    )

    assert "At a glance" in body
    assert "Type:" in body and "Skill" in body
    assert "State:" in body and "clean" in body
    assert "Scope:" in body and "global" in body
    assert "Source & location" in body
    assert "Description" not in body
    assert "Skill [b]journal[/]" not in body


def test_asset_info_keeps_long_source_in_technical_details() -> None:
    source = "file:///tmp/fixture/a/very/long/source/path/that/does/not/fit/a/narrow/pane"
    body = asset_info_body(
        asset_label="Command",
        slug="review",
        description="A concise description.",
        description_location="command markdown",
        source=source,
        origin="catalog",
        ref="feature/a-very-long-ref",
        state="installed",
        scope="project",
    )

    assert "Description" in body
    assert "Technical details" in body
    assert source in body
    assert "…" in body


def test_asset_info_escapes_malformed_markup_after_truncation() -> None:
    raw = "x" * 29 + "[/b]" + "y" * 26
    body = asset_info_body(
        asset_label="Skill",
        slug="malformed",
        description=None,
        description_location="SKILL.md",
        source=raw,
        origin="local",
        ref="[unterminated",
        state="clean",
        scope="global",
    )

    plain = Text.from_markup(body).plain
    assert raw in plain
    assert "[unterminated" in plain
    assert "Technical details" in plain


def test_escaped_extra_path_is_deduplicated_and_cannot_activate_markup(tmp_path: Path) -> None:
    raw = "x" * 29 + "[/b]" + "y" * 26
    path = tmp_path / raw
    body = asset_info_body(
        asset_label="Skill",
        slug="bracket-path",
        description=None,
        description_location="SKILL.md",
        source=str(path),
        origin="local",
        ref=None,
        state="local files (read-only)",
        scope="global",
        extra_lines=local_path_info(path),
    )

    plain = Text.from_markup(body).plain
    assert f"Full source: {path}" in plain
    assert f"Source path: {path}" not in plain
    assert "Technical details" in plain


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("settings_path", "spec"),
    [
        ("/tmp/[/b]/settings.json", "../local-[/b]"),
        (r"C:\[repo]\settings.json", r"..\\[repo]\\package"),
    ],
)
async def test_pi_local_package_info_renders_settings_and_spec_as_literal_text(
    settings_path: str, spec: str,
) -> None:
    """PiGrid.action_info must hand literal local-package facts to its modal."""
    from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
    from agent_toolkit_tui.widgets.pi_grid import PiGrid

    cell = PiCell(True, False, "local-package", managed=False,
                  package_spec=spec, config_path=settings_path)
    row = PiExtensionRow(
        slug="local-package",
        origin="local-package",
        source=spec,
        global_cell=cell,
        project_cell=cell,
        managed=False,
        global_package_spec=spec,
        global_config_path=settings_path,
    )
    grid = PiGrid([row])

    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    async with _App().run_test() as pilot:
        await pilot.pause()
        grid.query_one(DataTable).cursor_coordinate = Coordinate(0, 0)
        grid.action_info()
        await pilot.pause()
        plain = grid.app.screen.query_one("#cell-info-body", Static).render().plain

    assert f"Source: {spec}" in plain
    assert f"Manual removal: edit {settings_path} and remove the packages[] entry" in plain
    assert f"whose source is {spec!r} (or the matching string entry)." in plain


@pytest.mark.parametrize("grid_kind", ["agent", "command", "pi-extension"])
async def test_catalogue_info_renders_brackets_and_backslashes_once(grid_kind: str) -> None:
    """The shared catalogue producer and each consumer preserve literal facts."""
    from dataclasses import replace

    from agent_toolkit_cli.skill_catalog import CatalogEntry, safe_source
    from agent_toolkit_tui.agent_state import AgentCell, AgentRow
    from agent_toolkit_tui.command_state import CommandCell, CommandRow
    from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
    from agent_toolkit_tui.widgets.agent_grid import AgentGrid
    from agent_toolkit_tui.widgets.command_grid import CommandGrid
    from agent_toolkit_tui.widgets.pi_grid import PiGrid

    upstream = r"https://example/[repo]\\\\" + "branch/" * 8
    directory = "dir\n[/b]"
    source = replace(safe_source("https://example/owner/repo"), url=upstream, subpath=directory)
    item = CatalogEntry("literal", "Description [/b]", source, kind=grid_kind)
    if grid_kind == "agent":
        grid = AgentGrid([AgentRow(
            slug="literal", source=upstream, ref="main", state="catalog",
            cells={("pi", "global"): AgentCell(False)}, catalog_item=item,
            catalog_url=upstream, catalog_only=True,
        )])
    elif grid_kind == "command":
        grid = CommandGrid([CommandRow(
            slug="literal", source=upstream, ref="main", state="catalog",
            cells={("pi", "global"): CommandCell(False)}, catalog_item=item,
            catalog_url=upstream, catalog_only=True,
        )])
    else:
        cell = PiCell(False, False, "catalog")
        grid = PiGrid([PiExtensionRow(
            slug="literal", origin="catalog", source=upstream,
            global_cell=cell, project_cell=cell, catalog_item=item,
            catalog_url=upstream, catalog_only=True,
        )])

    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    async with _App().run_test() as pilot:
        await pilot.pause()
        grid.query_one(DataTable).cursor_coordinate = Coordinate(0, 0)
        grid.action_info()
        await pilot.pause()
        plain = grid.app.screen.query_one("#cell-info-body", Static).render().plain

    assert f"Catalog: {upstream}" in plain
    assert f"Upstream: {upstream}" in plain
    assert f"Directory: {directory}" in plain
    assert "Description [/b]" in plain
    assert "Technical details" in plain


async def test_skill_info_renders_colon_emoji_path_as_literal_text(tmp_path: Path) -> None:
    """CellInfoScreen must not apply Rich emoji substitution to source paths."""
    from agent_toolkit_tui.skill_state import SkillCell, SkillRow
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid

    path = tmp_path / ":warning:"
    grid = SkillGrid([SkillRow(
        "literal", str(path), "(untracked)", "unlisted",
        {("standard", "global"): SkillCell(False, False, False)},
    )])

    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    async with _App().run_test() as pilot:
        await pilot.pause()
        grid.action_info()
        await pilot.pause()
        plain = grid.app.screen.query_one("#cell-info-body", Static).render().plain

    assert str(path) in plain
    assert "⚠" not in plain


async def test_skill_catalogue_info_renders_literal_skill_path() -> None:
    """SkillGrid.action_info must escape catalogue subpaths at their boundary."""
    from dataclasses import replace

    from agent_toolkit_cli.skill_catalog import CatalogSkill, safe_source
    from agent_toolkit_tui.skill_state import SkillCell, SkillRow
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid

    source = replace(safe_source("https://example/owner/repo"), subpath="dir\n[/b]")
    item = CatalogSkill("literal", "", source)
    grid = SkillGrid([SkillRow(
        "literal", source.url, "main", "catalog",
        {("standard", "global"): SkillCell(False, False, False)},
        skill_path="dir\n[/b]", catalog_item=item, catalog_url="https://example/catalog",
        origin="catalog",
    )])

    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    async with _App().run_test() as pilot:
        await pilot.pause()
        grid.action_info()
        await pilot.pause()
        plain = grid.app.screen.query_one("#cell-info-body", Static).render().plain

    assert "Skill path: dir\n[/b]" in plain


async def test_instruction_info_preserves_raw_backslash_bracket_canonical_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_toolkit_tui.instruction_state import InstructionRow
    from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
    from agent_toolkit_cli import instructions_paths

    canonical = Path(r"C:\[repo]\AGENTS.md")
    monkeypatch.setattr(instructions_paths, "global_canonical_agents_md", lambda: canonical)
    grid = InstructionGrid([InstructionRow("AGENTS.md", "AGENTS.md", True)])

    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    app = _App()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid.query_one(DataTable).cursor_coordinate = Coordinate(0, 0)
        grid.action_info()
        await pilot.pause()
        assert str(canonical) in Text.from_markup(app.screen._body_markup).plain


def test_asset_info_puts_full_technical_values_after_actions_and_warnings() -> None:
    body = asset_info_body(
        asset_label="Agent",
        slug="local-agent",
        description=None,
        description_location="agent definition",
        source="/" + "very-long/" * 10 + "agent.md",
        origin="local",
        ref=None,
        state="local files (read-only)",
        scope="global",
        extra_lines=[
            "Space → queue Enable (global)",
            "WARNING: manual removal permanently deletes these files.",
        ],
    )

    assert body.index("Available actions") < body.index("Warning") < body.index("Technical details")


def test_asset_info_separates_actions_and_warnings() -> None:
    body = asset_info_body(
        asset_label="Agent",
        slug="local-agent",
        description=None,
        description_location="agent definition",
        source="/tmp/local-agent.md",
        origin="local",
        ref=None,
        state="local files (read-only)",
        scope="global",
        extra_lines=[
            "WARNING: manual removal permanently deletes these files.",
            "Manual removal removes only this file:",
            "  rm -- /tmp/local-agent.md",
        ],
    )

    assert "Warning" in body
    assert "Available actions" in body
    assert "[reverse]" in body


@pytest.mark.parametrize("asset_type,column", [
    ("skill", "standard"),
    ("command", "standard"),
    ("agent", "state"),
    ("mcp", "standard"),
    ("pi-extension", "pi"),
])
def test_each_kind_column_info_has_structured_sections(asset_type: str, column: str) -> None:
    info = get_column_info(column, asset_type=asset_type, context={"scope": "project"})
    assert info.sections
    markup = info.body_markup
    assert "[b]" in markup
    assert "At a glance" in markup


@pytest.mark.asyncio
async def test_modals_expose_scroll_and_close_guidance_at_narrow_size() -> None:
    info = get_column_info("pi", asset_type="pi-extension", context={"scope": "project"})

    class _App(App[None]):
        def on_mount(self) -> None:
            self.push_screen(ColumnInfoModal(info))

    app = _App()
    async with app.run_test(size=(58, 20)) as pilot:
        await pilot.pause()
        panel = app.screen.query_one(VerticalScroll)
        outer = app.screen.children[0]
        assert outer.region.right <= app.screen.size.width
        assert outer.region.bottom <= app.screen.size.height
        assert panel.allow_vertical_scroll
        assert "scroll" in str(app.screen.query_one("#column-info-footer").render()).lower()
        before = panel.scroll_y
        await pilot.press("down")
        await pilot.pause()
        assert panel.scroll_y > before
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is app.screen_stack[0]


@pytest.mark.asyncio
async def test_asset_modal_has_scroll_guidance() -> None:
    class _App(App[None]):
        def on_mount(self) -> None:
            self.push_screen(CellInfoScreen(title="Asset · Skill", body_markup="\n".join("detail" for _ in range(40))))

    app = _App()
    async with app.run_test(size=(58, 20)) as pilot:
        await pilot.pause()
        panel = app.screen.query_one(VerticalScroll)
        assert panel.allow_vertical_scroll
        assert "scroll" in str(app.screen.query_one("#cell-info-footer").render()).lower()
