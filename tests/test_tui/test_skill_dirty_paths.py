"""Child status is path-local; parent status includes the complete checkout."""
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_lock import read_lock, write_lock
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_skill_collection_registration import source, git, invoke
from tests.test_cli.test_skill_collection_reconcile import legacy


@pytest.mark.parametrize(('scope', 'change', 'read_only'), [
    ('global', 'unstaged', True), ('global', 'staged', True),
    ('global', 'deleted', True), ('global', 'untracked', True),
    ('global', 'root', True), ('global', 'unstaged', False),
    ('project', 'unstaged', True), ('project', 'root', True),
])
def test_sibling_dirty_state_does_not_bleed(source, tmp_path, monkeypatch, scope, change, read_only):
    monkeypatch.setenv('HOME', str(tmp_path/'home'))
    upstream=Path(source.removeprefix('file://'))
    (upstream/'alpha/NOTES.md').write_text('tracked child notes\n')
    (upstream/'README.md').write_text('tracked root notes\n')
    git(upstream, 'add', '.')
    git(upstream, 'commit', '-qm', 'extra tracked paths')
    added=invoke(source)
    assert added.exit_code == 0, added.output
    lock=read_lock(library_lock_path())
    for entry in lock.skills.values():
        entry.read_only=read_only
    write_lock(library_lock_path(), lock)
    project=tmp_path/'project';project.mkdir()
    runner=CliRunner()
    if scope == 'project':
        for slug in ('alpha', 'beta'):
            enabled=runner.invoke(main, ['--project',str(project),'skills','install',slug,'--scope','project','--agents','standard'])
            assert enabled.exit_code == 0, enabled.output
    backing=library_skill_path('alpha').resolve().parent
    if change == 'root':
        (backing/'README.md').write_text('root changed\n')
    elif change == 'deleted':
        (backing/'alpha/NOTES.md').unlink()
    elif change == 'untracked':
        (backing/'alpha/new.txt').write_text('untracked child content\n')
    else:
        (backing/'alpha/SKILL.md').write_text('---\nname: alpha\n---\nchanged\n')
        if change == 'staged':
            git(backing, 'add', 'alpha/SKILL.md')
    index=(backing/'.git/index').read_bytes()
    rows=build_skill_rows(scope=scope,home=Path.home(),project=project if scope=='project' else None)
    states={r.slug:r.state for r in rows}
    assert states == {'alpha':'clean' if change=='root' else 'dirty','beta':'clean'}
    result=runner.invoke(main,['--project',str(project),'skills','status','alpha','beta','-p' if scope=='project' else '-g'])
    assert result.exit_code == 0, result.output
    assert f"alpha\t{'clean' if change=='root' else 'dirty'}" in result.output
    assert 'beta\tclean' in result.output
    grid=SkillGrid(rows)
    parent=next(r for r in grid._visible_rows() if r.is_collection)
    assert parent.state == 'dirty'
    # Filtering out the edited child must not make the repository look clean.
    grid._filter='beta'
    assert next(r for r in grid._visible_rows() if r.is_collection).state == 'dirty'
    assert (backing/'.git/index').read_bytes() == index


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['child', 'root'])
async def test_parent_and_child_badges_render_actual_git_states(legacy, change):
    from textual.app import App
    from textual.widgets import DataTable
    from rich.text import Text

    target = legacy/'workflow-00/SKILL.md' if change == 'child' else legacy/'README.md'
    target.write_text('local change\n')
    rows = build_skill_rows(scope='global', home=Path.home(), project=None)

    class GridApp(App):
        def compose(self):
            yield SkillGrid(rows)

    app = GridApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        table = grid.query_one(DataTable)
        states = [Text.from_markup(str(table.get_row_at(i)[-2])).plain for i in range(table.row_count)]
        assert states == ['dirty', 'dirty' if change == 'child' else 'clean'] + ['clean']*10


def test_legacy_derived_children_have_independent_status(legacy):
    (legacy/'workflow-00/SKILL.md').write_text('changed child\n')
    rows=build_skill_rows(scope='global',home=Path.home(),project=None)
    assert {r.slug:r.state for r in rows} == {
        f'workflow-{i:02}':'dirty' if i==0 else 'clean' for i in range(11)
    }
    assert next(r for r in SkillGrid(rows)._visible_rows() if r.is_collection).state == 'dirty'
