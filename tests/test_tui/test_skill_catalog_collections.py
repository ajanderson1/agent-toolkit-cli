"""Advertised collections use real disposable Git sources and the real Textual grid."""
import json
from dataclasses import replace

import pytest

from agent_toolkit_cli.skill_catalog import read_catalog, parse_catalog, CatalogSnapshot
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from agent_toolkit_tui.app import TUIApp
from textual.coordinate import Coordinate
from tests.test_cli.test_reground import sandbox, git, invoke
from tests.test_cli.test_skill_catalog_acquire import subscribed


def advertise(cat, upstream, children=('demo', 'other')):
    items = [dict(key=name, description=name, source=upstream.as_uri(), path=f'skills/{name}', ref='main') for name in children]
    (cat / 'catalog.json').write_text(json.dumps(dict(version=1, skills=items)))
    git(cat, 'add', '.')
    git(cat, '-c', 'user.name=Test', '-c', 'user.email=test@example.test', 'commit', '-m', 'list children')


def rows(home, project=None, snapshot=None):
    return build_skill_rows(scope='project' if project else 'global', home=home, project=project, catalog_snapshot=snapshot if snapshot is not None else read_catalog(home=home))


def test_catalog_only_siblings_form_one_collection(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    advertise(cat, upstream)
    grid = SkillGrid(rows(sandbox))
    assert grid.collection_count == 1
    assert sum(r.is_collection for r in grid._visible_rows()) == 1
    assert {r.slug for r in grid._rows} == {'demo', 'other'}
    assert not (sandbox / '.agent-toolkit/skills-lock.json').exists()
    assert not (sandbox / '.agent-toolkit/skills').exists()


def test_mixed_collection_reuses_custom_slug_without_writes(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    advertise(cat, upstream)
    invoke('skills', 'add', upstream.as_uri(), '--path', 'skills/demo', '--slug', 'custom', '--ref', 'main')
    lock = sandbox / '.agent-toolkit/skills-lock.json'
    before = lock.read_bytes()
    grid = SkillGrid(rows(sandbox))
    assert grid.collection_count == 1
    assert {r.slug for r in grid._rows} == {'custom', 'other'}
    assert next(r for r in grid._rows if r.slug == 'custom').origin == 'library'
    assert lock.read_bytes() == before


def test_distinct_hosts_refs_and_slug_conflicts_do_not_merge(sandbox):
    data = dict(version=1, skills=[
        dict(key=k, description=k, source=url, path=path, ref=ref)
        for k, url, path, ref in [
            ('one','https://one.example/team/repo.git','skills/a','v1'),
            ('two','https://one.example/team/repo.git','skills/b','v1'),
            ('foreign','https://two.example/team/repo.git','skills/a','v1'),
            ('different-ref','https://one.example/team/repo.git','skills/a','v2'),
        ]])
    result = rows(sandbox, snapshot=CatalogSnapshot('catalog', skills=parse_catalog(data)))
    by_slug = {r.slug:r for r in result}
    assert by_slug['one'].collection_key is not None
    assert by_slug['one'].collection_key == by_slug['two'].collection_key
    assert by_slug['foreign'].collection_key != by_slug['one'].collection_key
    assert by_slug['different-ref'].collection_key != by_slug['one'].collection_key


def test_exact_selector_aliases_have_one_actionable_row(sandbox):
    base = dict(description='alias', source='https://host.example/team/repo.git', path='skills/a', ref='v1')
    snapshot = CatalogSnapshot('catalog', skills=parse_catalog(dict(version=1,skills=[dict(base,key='zeta'),dict(base,key='alpha')])))
    result = rows(sandbox, snapshot=snapshot)
    assert len(result) == 1
    assert result[0].slug == 'alpha'
    assert not (sandbox / '.agent-toolkit/skills-lock.json').exists()


def test_individual_add_then_full_repo_add_folds_without_reacquisition(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path)
    advertise(cat, upstream)
    invoke('skills','add',upstream.as_uri(),'--path','skills/demo','--slug','custom','--ref','main')
    project = tmp_path / 'project'; project.mkdir(); monkeypatch.chdir(project)
    invoke('skills','install','custom','--scope','project','--agents','standard')
    backing = (sandbox/'.agent-toolkit/skills/custom').resolve().parent.parent
    (backing/'local.txt').write_text('preserve')
    before = (git(backing,'rev-parse','HEAD'),(backing/'.git/index').read_bytes())
    invoke('skills','add',upstream.as_uri(),'--ref','main')
    grid = SkillGrid(rows(sandbox, project))
    assert grid.collection_count == 1
    assert {r.slug for r in grid._rows} == {'custom','other'}
    assert (project/'.agents/skills/custom').exists()
    assert not (project/'.agents/skills/other').exists()
    assert before == (git(backing,'rev-parse','HEAD'),(backing/'.git/index').read_bytes())
    assert (backing/'local.txt').read_text() == 'preserve'
    invoke('skills','remove','other','--force')
    offered = next(r for r in rows(sandbox, project) if r.slug=='other')
    assert offered.origin == 'catalog'


@pytest.mark.asyncio
async def test_parent_all_captures_hidden_supported_children(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path); advertise(cat, upstream)
    monkeypatch.chdir(tmp_path)
    async with TUIApp().run_test() as pilot:
        app = pilot.app
        await app.workers.wait_for_complete(); await pilot.pause()
        grid = app.query_one(SkillGrid)
        grid.set_filter('demo')
        grid._toggle_at(Coordinate(0, 0))  # collapse does not narrow membership
        grid._toggle_at(Coordinate(0, 1))
        assert grid.pending_entries() == {('project','standard','demo'):'link',('project','standard','other'):'link'}
        intents = grid.pending_skill_intents()
        assert intents[('project','standard','other')].identity[2] == 'skills/other'
        assert not (sandbox/'.agent-toolkit/skills-lock.json').exists()
        app.action_revert()
        assert not grid.pending_entries()
        assert not grid.pending_skill_intents()
        assert not (sandbox/'.agent-toolkit/skills-lock.json').exists()


@pytest.mark.asyncio
async def test_collapse_filter_and_late_snapshot_preserve_exact_intents(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path); advertise(cat, upstream)
    monkeypatch.chdir(tmp_path)
    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete(); await pilot.pause()
        grid = app.query_one(SkillGrid)
        grid.cursor_to_cell(row_slug='demo',agent_name='standard'); grid.action_toggle_cell()
        original = grid.pending_skill_intents()
        assert original[('project','standard','demo')].identity[2]=='skills/demo'
        grid.set_filter('other')
        advertise(cat, upstream, ('other',))
        app._refresh_skill_view()
        await app.workers.wait_for_complete(); await pilot.pause()
        assert grid.pending_entries()=={('project','standard','demo'):'link'}
        assert grid.pending_skill_intents()==original
        assert not (sandbox/'.agent-toolkit/skills-lock.json').exists()


@pytest.mark.asyncio
async def test_new_advertisement_does_not_join_pending_all(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path); advertise(cat, upstream)
    monkeypatch.chdir(tmp_path)
    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete(); await pilot.pause()
        grid = app.query_one(SkillGrid); grid._toggle_at(Coordinate(0, 1))
        before = grid.pending_entries()
        advertise(cat, upstream, ('demo','other','later'))
        app._refresh_skill_view()
        await app.workers.wait_for_complete(); await pilot.pause()
        assert grid.pending_entries()==before
        assert set(grid.pending_skill_intents())==set(before)
        assert ('project','standard','later') not in grid.pending_entries()


def test_selector_alias_does_not_bypass_stable_catalog_association(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    invoke('skills','catalog','add','demo')
    item = dict(description='changed',source=upstream.as_uri(),path='skills/other',ref='main')
    snapshot = CatalogSnapshot(cat.as_uri(), skills=parse_catalog(dict(version=1,skills=[dict(item,key='aaa'),dict(item,key='demo')])))
    result = rows(sandbox, snapshot=snapshot)
    assert [r.slug for r in result]==['demo']
    assert 'selector changed' in result[0].catalog_warning


@pytest.mark.asyncio
@pytest.mark.parametrize('all_children', [False, True])
async def test_all_fetches_catalog_once_and_acquires_only_selected_children(tmp_path, sandbox, monkeypatch, all_children):
    import agent_toolkit_cli.skill_catalog as transport
    upstream, cat = subscribed(tmp_path); advertise(cat, upstream)
    monkeypatch.chdir(tmp_path)
    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete(); await pilot.pause()
        grid = app.query_one(SkillGrid)
        if all_children: grid._toggle_at(Coordinate(0,1))
        else:
            grid.cursor_to_cell(row_slug='demo',agent_name='standard'); grid.action_toggle_cell()
        fetched=[]; original=transport.fetch_catalog
        def fetch(*args, **kwargs):
            fetched.append(args[0]); return original(*args, **kwargs)
        monkeypatch.setattr(transport,'fetch_catalog',fetch)
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete(); await pilot.pause()
        assert not result.failed, result.errors
        expected={'demo','other'} if all_children else {'demo'}
        assert set(json.loads((sandbox/'.agent-toolkit/skills-lock.json').read_text())['skills'])==expected
        assert (tmp_path/'.agents/skills/demo').exists()
        assert (tmp_path/'.agents/skills/other').exists()==all_children
        assert len(fetched)==2  # one Apply snapshot, one inventory refresh
        assert not grid.pending_entries()


@pytest.mark.asyncio
@pytest.mark.parametrize('existing', [False, True])
async def test_one_failed_acquisition_leaves_collection_enablement_unchanged(tmp_path, sandbox, monkeypatch, existing):
    import agent_toolkit_cli.skill_catalog_ops as ops
    upstream, cat = subscribed(tmp_path); advertise(cat, upstream)
    monkeypatch.chdir(tmp_path)
    if existing: invoke('skills','catalog','enable','demo','--scope','project','--agents','standard')
    app=TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete(); await pilot.pause()
        grid=app.query_one(SkillGrid)
        for slug in ('demo','other'):
            grid.cursor_to_cell(row_slug=slug,agent_name='standard');grid.action_toggle_cell()
        pending=grid.pending_entries();original=ops.acquire_catalog_skill
        def acquire(item, **kwargs):
            if item.key=='other': raise ValueError('injected acquisition failure')
            return original(item, **kwargs)
        monkeypatch.setattr(ops,'acquire_catalog_skill',acquire)
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert result.failed==2
        assert (tmp_path/'.agents/skills/demo').exists()==existing
        assert not (tmp_path/'.agents/skills/other').exists()
        assert set(json.loads((sandbox/'.agent-toolkit/skills-lock.json').read_text())['skills'])=={'demo'}
        assert grid.pending_entries()==pending
        monkeypatch.setattr(ops,'acquire_catalog_skill',original)
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert not result.failed, result.errors
        assert (tmp_path/'.agents/skills/demo').exists()==(not existing)
        assert (tmp_path/'.agents/skills/other').exists()
        assert not grid.pending_entries()


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation', ['removed','selector','subscription'])
async def test_stale_collection_refuses_before_acquisition(tmp_path, sandbox, monkeypatch, mutation):
    upstream, cat=subscribed(tmp_path);advertise(cat,upstream);monkeypatch.chdir(tmp_path)
    app=TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete();await pilot.pause()
        grid=app.query_one(SkillGrid);grid._toggle_at(Coordinate(0,1));pending=grid.pending_entries()
        if mutation=='removed': advertise(cat,upstream,('demo',))
        elif mutation=='subscription': invoke('skills','catalog','subscribe',cat.as_uri(),'--ref','main')
        else:
            data=json.loads((cat/'catalog.json').read_text());data['skills'][1]['path']='skills/demo'
            (cat/'catalog.json').write_text(json.dumps(data));git(cat,'add','.');git(cat,'-c','user.name=Test','-c','user.email=test@example.test','commit','-m','changed selector')
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert result.failed==2
        assert not (sandbox/'.agent-toolkit/skills-lock.json').exists()
        assert not (tmp_path/'.agents/skills/demo').exists()
        assert grid.pending_entries()==pending


@pytest.mark.asyncio
async def test_unrelated_collection_can_succeed(tmp_path, sandbox, monkeypatch):
    from tests.test_cli.test_reground import repo
    upstream,cat=subscribed(tmp_path);advertise(cat,upstream);monkeypatch.chdir(tmp_path)
    other_root=tmp_path/'independent';other_root.mkdir()
    independent=repo(other_root,{'SKILL.md':'---\nname: standalone\ndescription: standalone\n---\n'})
    invoke('skills','add',independent.as_uri(),'--slug','standalone')
    import agent_toolkit_cli.skill_catalog_ops as ops
    original=ops.acquire_catalog_skill
    def fail(item, **kwargs):
        if item.key=='other': raise ValueError('injected')
        return original(item, **kwargs)
    app=TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete();await pilot.pause()
        grid=app.query_one(SkillGrid)
        for slug in ('demo','other','standalone'):
            grid.cursor_to_cell(row_slug=slug,agent_name='standard');grid.action_toggle_cell()
        monkeypatch.setattr(ops,'acquire_catalog_skill',fail)
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert result.failed==2
        assert (tmp_path/'.agents/skills/standalone').exists()
        assert not (tmp_path/'.agents/skills/demo').exists()
        assert {key[2] for key in grid.pending_entries()}=={'demo','other'}


@pytest.mark.asyncio
async def test_projection_failure_restores_all_requested_harnesses_and_retry_succeeds(tmp_path,sandbox,monkeypatch):
    from agent_toolkit_cli.skill_collection_transaction import Journal
    from agent_toolkit_cli.skill_collections import projection
    upstream,cat=subscribed(tmp_path);advertise(cat,upstream);monkeypatch.chdir(tmp_path)
    app=TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete();await pilot.pause()
        grid=app.query_one(SkillGrid)
        extra=next(a for a in grid._active_agents() if a!='standard')
        for slug in ('demo','other'):
            for agent in ('standard',extra):
                grid.cursor_to_cell(row_slug=slug,agent_name=agent);grid.action_toggle_cell()
        pending=grid.pending_entries();assert len(pending)==4
        original=Journal.link;writes=[]
        def link(journal,path,before,after):
            if after is not None and path.is_relative_to(tmp_path) and path.is_relative_to(tmp_path/'.agent-toolkit') is False and path.is_relative_to(sandbox) is False:
                writes.append(path)
                if len(writes)==2: raise OSError('injected projection failure')
            return original(journal,path,before,after)
        monkeypatch.setattr(Journal,'link',link)
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert result.failed==4
        for slug in ('demo','other'):
            for agent in ('standard',extra):
                assert not projection(slug,agent,scope='project',home=sandbox,project=tmp_path).exists()
        assert grid.pending_entries()==pending
        before=(sandbox/'.agent-toolkit/skills-lock.json').read_bytes()
        monkeypatch.setattr(Journal,'link',original)
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert not result.failed,result.errors
        assert (sandbox/'.agent-toolkit/skills-lock.json').read_bytes()==before


@pytest.mark.asyncio
@pytest.mark.parametrize('hazard', ['foreign','root','local-root'])
async def test_unsafe_collection_preflight_precedes_acquisition(tmp_path,sandbox,monkeypatch,hazard):
    upstream,cat=subscribed(tmp_path);advertise(cat,upstream);monkeypatch.chdir(tmp_path)
    if hazard=='foreign':
        foreign=tmp_path/'.agents/skills/other';foreign.mkdir(parents=True);(foreign/'SKILL.md').write_text('foreign')
    else:
        (upstream/'SKILL.md').write_text('---\nname: root\ndescription: root\n---\n')
        git(upstream,'add','.');git(upstream,'-c','user.name=Test','-c','user.email=test@example.test','commit','-m','real root')
        data=json.loads((cat/'catalog.json').read_text());data['skills'][0]['path']='.'
        (cat/'catalog.json').write_text(json.dumps(data));git(cat,'add','.');git(cat,'-c','user.name=Test','-c','user.email=test@example.test','commit','-m','advertise root')
    if hazard=='local-root':invoke('skills','catalog','add','demo')
    library=sandbox/'.agent-toolkit/skills-lock.json'
    before=library.read_bytes() if library.exists() else None
    app=TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete();await pilot.pause()
        grid=app.query_one(SkillGrid)
        if hazard=='foreign':grid._toggle_at(Coordinate(0,1))
        else:
            grid.cursor_to_cell(row_slug='demo',agent_name='standard');grid.action_toggle_cell()
        if hazard=='local-root':cat.rename(tmp_path/'offline')
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert result.failed
        assert (library.read_bytes() if library.exists() else None)==before
        assert not (tmp_path/'.agents/skills/demo').exists()
        if hazard=='foreign':assert (foreign/'SKILL.md').read_text()=='foreign'


@pytest.mark.asyncio
async def test_local_identity_change_blocks_collection_and_offline_local_only_still_works(tmp_path,sandbox,monkeypatch):
    upstream,cat=subscribed(tmp_path);advertise(cat,upstream);monkeypatch.chdir(tmp_path)
    invoke('skills','catalog','enable','demo','--scope','project','--agents','standard')
    app=TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete();await pilot.pause()
        grid=app.query_one(SkillGrid)
        for slug in ('demo','other'):
            grid.cursor_to_cell(row_slug=slug,agent_name='standard');grid.action_toggle_cell()
        from agent_toolkit_cli.skill_lock import read_lock,write_lock
        path=sandbox/'.agent-toolkit/skills-lock.json';lock=read_lock(path)
        entry=lock.skills['demo'];lock.skills['demo']=replace(entry,ref='changed')
        write_lock(path,lock)
        # Also change the project record, since it owns this scope's identity.
        scoped=tmp_path/'skills-lock.json';project_lock=read_lock(scoped)
        old=project_lock.skills['demo'];project_lock.skills['demo']=replace(old,ref='changed');write_lock(scoped,project_lock)
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert result.failed==2
        assert (tmp_path/'.agents/skills/demo').exists()
        assert not (sandbox/'.agent-toolkit/skills/other').exists()
        lock.skills['demo']=entry;write_lock(path,lock)
        project_lock.skills['demo']=old;write_lock(scoped,project_lock)
        app.action_revert();app._refresh_skill_view()
        await app.workers.wait_for_complete();await pilot.pause()
        grid.cursor_to_cell(row_slug='demo',agent_name='standard');grid.action_toggle_cell()
        cat.rename(tmp_path/'offline')
        result=app._apply_skill_pending()
        await app.workers.wait_for_complete();await pilot.pause()
        assert not result.failed,result.errors
        assert not (tmp_path/'.agents/skills/demo').exists()
        assert (sandbox/'.agent-toolkit/skills/demo/SKILL.md').is_file()
