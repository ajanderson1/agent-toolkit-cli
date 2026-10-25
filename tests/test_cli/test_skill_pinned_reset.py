"""Real-Git regressions for configured reset/update targets, not origin/SHA."""
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path
from tests.test_cli.test_skill_collection_registration import source, git, invoke


@pytest.mark.parametrize('selector', ['sha', 'short-sha', 'tag', 'hex-branch'])
def test_force_reset_restores_configured_parent_target(source, selector):
    upstream = Path(source.removeprefix('file://'))
    pin = git(upstream, 'rev-parse', 'HEAD')
    ref = pin if selector == 'sha' else pin[:12] if selector == 'short-sha' else 'v1.0' if selector == 'tag' else 'dead123'
    if selector == 'tag':
        git(upstream, 'tag', '-a', ref, '-m', 'pinned release')
    elif selector == 'hex-branch':
        git(upstream, 'branch', ref)
    added = invoke(source, '--ref', ref)
    assert added.exit_code == 0, added.output
    backing = library_skill_path('alpha').resolve().parent
    original = {s: (backing/s/'SKILL.md').read_bytes() for s in ('alpha', 'beta')}
    (backing/'local-commit.txt').write_text('local commit\n')
    git(backing, 'add', '.')
    git(backing, 'commit', '-qm', 'local commit to discard')
    (backing/'alpha/SKILL.md').write_text('staged edit\n')
    git(backing, 'add', 'alpha/SKILL.md')
    (backing/'alpha/SKILL.md').write_text('unstaged over index\n')
    (backing/'beta/SKILL.md').write_text('sibling edit\n')
    (backing/'notes.txt').write_text('untracked notes survive\n')
    (upstream/'new-main.txt').write_text('new upstream main\n')
    git(upstream, 'add', '.')
    git(upstream, 'commit', '-qm', 'advance main beyond the pin')

    result = CliRunner().invoke(main, ['skills', 'reset', 'alpha', '-g', '--force'])

    assert result.exit_code == 0, result.output
    assert git(backing, 'rev-parse', 'HEAD') == pin
    assert not (backing/'new-main.txt').exists()
    assert not (backing/'local-commit.txt').exists()
    assert (backing/'notes.txt').read_text() == 'untracked notes survive\n'
    assert {s: (backing/s/'SKILL.md').read_bytes() for s in ('alpha', 'beta')} == original
    assert git(backing, 'diff', '--cached', '--name-only') == ''
    lock = read_lock(library_lock_path())
    assert lock.skills['alpha'].ref == ref
    assert lock.skills['alpha'].upstream_sha == pin
    assert lock.skills['beta'].ref == ref


def test_pinned_update_preserves_local_edits_and_pin(source):
    upstream = Path(source.removeprefix('file://'))
    pin = git(upstream, 'rev-parse', 'HEAD')
    added = invoke(source, '--ref', pin)
    assert added.exit_code == 0, added.output
    backing = library_skill_path('alpha').resolve().parent
    (backing/'alpha/SKILL.md').write_text('keep my edit\n')
    (upstream/'later.txt').write_text('not selected by pin\n')
    git(upstream, 'add', '.')
    git(upstream, 'commit', '-qm', 'advance upstream')
    result = CliRunner().invoke(main, ['skills', 'update', 'alpha', '-g'])
    assert result.exit_code == 0, result.output
    assert git(backing, 'rev-parse', 'HEAD') == pin
    assert (backing/'alpha/SKILL.md').read_text() == 'keep my edit\n'
    assert not (backing/'later.txt').exists()
    assert read_lock(library_lock_path()).skills['alpha'].ref == pin


def test_pinned_standalone_add_and_force_reset(git_sandbox, tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_TOOLKIT_SKILLS_ROOT', str(tmp_path/'library/skills'))
    pin = git(git_sandbox.clone, 'rev-parse', 'HEAD')
    runner = CliRunner()
    added = runner.invoke(main, ['skills', 'add', str(git_sandbox.upstream), '--slug', 'single', '--ref', pin])
    assert added.exit_code == 0, added.output
    backing = library_skill_path('single')
    original = (backing/'SKILL.md').read_bytes()
    (backing/'SKILL.md').write_text('discard me\n')
    result = runner.invoke(main, ['skills', 'reset', 'single', '-g', '--force'])
    assert result.exit_code == 0, result.output
    assert (backing/'SKILL.md').read_bytes() == original
    assert git(backing, 'rev-parse', 'HEAD') == pin
    entry = read_lock(library_lock_path()).skills['single']
    assert entry.ref == pin and entry.local_sha == entry.upstream_sha == pin


def test_pinned_standalone_update_keeps_edits(git_sandbox, tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_TOOLKIT_SKILLS_ROOT', str(tmp_path/'library/skills'))
    pin = git(git_sandbox.clone, 'rev-parse', 'HEAD')
    runner = CliRunner()
    added = runner.invoke(main, ['skills', 'add', str(git_sandbox.upstream), '--slug', 'single', '--ref', pin])
    assert added.exit_code == 0, added.output
    backing = library_skill_path('single')
    (backing/'SKILL.md').write_text('keep local edits\n')
    result = runner.invoke(main, ['skills', 'update', 'single', '-g'])
    assert result.exit_code == 0, result.output
    assert (backing/'SKILL.md').read_text() == 'keep local edits\n'
    assert git(backing, 'rev-parse', 'HEAD') == pin
    entry = read_lock(library_lock_path()).skills['single']
    assert entry.ref == pin and entry.local_sha == entry.upstream_sha == pin


def test_missing_branch_does_not_reset_to_same_named_tag(source, tmp_path):
    clone = tmp_path/'clone'
    git(tmp_path, 'clone', source, str(clone))
    git(clone, 'tag', 'main')
    (clone/'local.txt').write_text('local commit\n')
    git(clone, 'add', '.')
    git(clone, 'commit', '-qm', 'local work')
    git(clone, 'update-ref', '-d', 'refs/remotes/origin/main')
    (clone/'alpha/SKILL.md').write_text('preserve on missing branch\n')
    before = git(clone, 'rev-parse', 'HEAD')
    with pytest.raises(skill_git.GitError):
        skill_git.reset_hard(clone, ref='main', env=None)
    assert git(clone, 'rev-parse', 'HEAD') == before
    assert (clone/'alpha/SKILL.md').read_text() == 'preserve on missing branch\n'


def test_invalid_reset_target_preserves_dirty_tree(source, tmp_path):
    clone = tmp_path/'clone'
    git(tmp_path, 'clone', source, str(clone))
    (clone/'alpha/SKILL.md').write_text('preserve on invalid target\n')
    before = git(clone, 'rev-parse', 'HEAD')
    with pytest.raises(skill_git.GitError):
        skill_git.reset_hard(clone, ref='0'*40, env=None)
    assert git(clone, 'rev-parse', 'HEAD') == before
    assert (clone/'alpha/SKILL.md').read_text() == 'preserve on invalid target\n'
