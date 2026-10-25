"""Advertised collections use real disposable Git sources and the real Textual grid."""
import json
from dataclasses import replace

import pytest

from agent_toolkit_cli.skill_catalog import read_catalog, parse_catalog, CatalogSnapshot
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
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
