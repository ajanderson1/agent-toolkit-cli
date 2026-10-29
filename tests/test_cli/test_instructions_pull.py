"""Host deployment uses real Git objects and never touches the real HOME."""
from __future__ import annotations

import hashlib
import json
import subprocess

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli import instructions_source as source
from tests.test_cli.test_instructions_lockless import snapshot


@pytest.fixture
def deployment(tmp_path, monkeypatch, git_sandbox):
    home = tmp_path / 'deploy-home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    repo = git_sandbox.clone
    directory = repo / 'agents-instructions'
    directory.mkdir()
    (directory / 'AGENTS.atlas.md').write_text('# Atlas v1\n')
    (directory / 'AGENTS.k2.md').write_text('# K2\n')

    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True,
                              env=git_sandbox.env, capture_output=True, text=True).stdout.strip()

    git('add', '.')
    git('commit', '-m', 'host instructions')
    sha = git('rev-parse', 'HEAD')
    git('tag', 'instructions/atlas/v1.0.0')
    canonical = home / '.agent-toolkit/AGENTS.md'
    return home, repo, canonical, sha, git


def pull(deployment, *args, input=None):
    _, repo, _, _, _ = deployment
    return CliRunner().invoke(main, ['instructions', 'pull', '--source', str(repo),
                                    '--host', 'atlas', '--ref', 'instructions/atlas/v1.0.0',
                                    *args], input=input)


def records(home):
    return sorted((home / '.agent-toolkit/instructions-deployments').glob('*/deployment.json'))


def test_pinned_one_host_global_content_and_provenance(deployment):
    home, repo, canonical, sha, git = deployment
    (repo / 'agents-instructions/AGENTS.atlas.md').write_text('# Atlas newer\n')
    git('add', '.')
    git('commit', '-m', 'newer content')
    # Even a dirty checkout cannot change the chosen committed source.
    (repo / 'agents-instructions/AGENTS.atlas.md').write_text('# Dirty\n')
    result = pull(deployment, '--yes')
    assert result.exit_code == 0, result.output
    assert canonical.read_text() == '# Atlas v1\n'
    assert sha in result.output
    receipt = json.loads(records(home)[0].read_text())
    assert receipt['commit'] == sha
    assert receipt['host'] == 'atlas'
    assert receipt['sha256'] == hashlib.sha256(canonical.read_bytes()).hexdigest()
    assert receipt['path'] == 'agents-instructions/AGENTS.atlas.md'
    assert not list(home.rglob('*lock*'))
    assert not (home / '.pi').exists()


@pytest.mark.parametrize('args,input', [(('--dry-run',), None), ((), 'n\n'), ((), None)])
def test_preview_decline_or_noninteractive_is_read_only(deployment, args, input):
    home, _, _, _, _ = deployment
    before = snapshot(home)
    result = pull(deployment, *args, input=input)
    assert 'Atlas v1' in result.output
    assert snapshot(home) == before


def test_replacement_requires_flag_and_retains_unique_backups(deployment):
    home, _, canonical, _, _ = deployment
    canonical.parent.mkdir()
    canonical.write_text('local work\n')
    assert pull(deployment, '--yes').exit_code != 0
    assert canonical.read_text() == 'local work\n'
    assert pull(deployment, '--replace', '--yes').exit_code == 0
    first = records(home)[0].parent
    assert (first / 'previous.md').read_text() == 'local work\n'
    assert pull(deployment, '--replace', '--yes').exit_code == 0
    assert len(records(home)) == 2
    assert (first / 'previous.md').read_text() == 'local work\n'
    result = CliRunner().invoke(main, ['instructions', 'restore', first.name,
                                     '--replace', '--yes'])
    assert result.exit_code == 0, result.output
    assert canonical.read_text() == 'local work\n'
    assert len(records(home)) == 3


@pytest.mark.parametrize('kind', ['symlink', 'dangling', 'directory'])
def test_canonical_conflicts_never_replaced(deployment, kind):
    home, _, canonical, _, _ = deployment
    canonical.parent.mkdir()
    if kind == 'directory':
        canonical.mkdir()
    else:
        foreign = home / 'foreign.md'
        if kind == 'symlink':
            foreign.write_text('foreign\n')
        canonical.symlink_to(foreign)
    before = snapshot(home)
    result = pull(deployment, '--replace', '--yes')
    assert result.exit_code != 0
    assert snapshot(home) == before


@pytest.mark.parametrize('body', [b'', b' \n', b'\xff', b'bad\0data', b'\x1b[31m',
                                  '\u009b31m'.encode(), b'x' * 262145],
                         ids=['empty', 'whitespace', 'invalid-utf8', 'nul',
                              'escape', 'c1-control', 'oversized'])
def test_invalid_blob_leaves_existing_content_unchanged(deployment, body):
    home, repo, canonical, _, git = deployment
    canonical.parent.mkdir()
    canonical.write_text('keep\n')
    (repo / 'agents-instructions/AGENTS.atlas.md').write_bytes(body)
    git('add', '.')
    git('commit', '-m', 'invalid blob')
    git('tag', '-f', 'instructions/atlas/v1.0.0')
    before = snapshot(home)
    assert pull(deployment, '--replace', '--yes').exit_code != 0
    assert snapshot(home) == before


def test_source_symlink_is_not_followed(deployment):
    home, repo, _, _, git = deployment
    path = repo / 'agents-instructions/AGENTS.atlas.md'
    path.unlink()
    path.symlink_to('AGENTS.k2.md')
    git('add', '.')
    git('commit', '-m', 'symlink source')
    git('tag', '-f', 'instructions/atlas/v1.0.0')
    before = snapshot(home)
    result = pull(deployment, '--yes')
    assert result.exit_code != 0 and 'regular' in result.output
    assert snapshot(home) == before


@pytest.mark.parametrize('flag,value', [('--host', '../k2'), ('--host', '-atlas'),
                                       ('--ref', '--upload-pack=evil'), ('--ref', 'main:other'),
                                       ('--source', 'ext::evil')])
def test_unsafe_arguments_are_rejected_without_mutation(deployment, flag, value):
    home, _, _, _, _ = deployment
    before = snapshot(home)
    result = pull(deployment, flag, value, '--yes')
    assert result.exit_code != 0
    assert snapshot(home) == before


def test_missing_source_file_and_ref_leave_home_unchanged(deployment):
    home, _, _, _, _ = deployment
    before = snapshot(home)
    assert pull(deployment, '--host', 'missing', '--yes').exit_code != 0
    assert pull(deployment, '--ref', 'not-a-ref', '--yes').exit_code != 0
    assert snapshot(home) == before


def test_existing_harness_pointers_and_project_are_preserved(deployment, monkeypatch, tmp_path):
    home, _, canonical, _, _ = deployment
    project = tmp_path / 'consumer'
    project.mkdir()
    (project / 'AGENTS.md').write_text('project only\n')
    monkeypatch.chdir(project)
    canonical.parent.mkdir()
    canonical.write_text('old global\n')
    pointer = home / '.pi/agent/AGENTS.md'
    pointer.parent.mkdir(parents=True)
    pointer.symlink_to(canonical)
    result = pull(deployment, '--replace', '--yes')
    assert result.exit_code == 0, result.output
    assert pointer.is_symlink() and pointer.read_text() == '# Atlas v1\n'
    assert (project / 'AGENTS.md').read_text() == 'project only\n'
    status = CliRunner().invoke(main, ['instructions', 'status', '--scope', 'global'])
    assert status.exit_code == 0 and 'ok' in status.output
    from agent_toolkit_tui.instruction_state import build_instruction_rows
    rows = build_instruction_rows(scope='global', home=home, project=None, selection=('pi',))
    assert len(rows) == 1 and rows[0].slug == 'AGENTS.md'
    assert rows[0].canonical_exists and rows[0].cells[('pi', 'global')].linked


def test_restore_rejects_paths_and_missing_backup(deployment):
    home, _, canonical, _, _ = deployment
    before = snapshot(home)
    for value in ['../outside', '/tmp/outside', 'not-present']:
        assert CliRunner().invoke(main, ['instructions', 'restore', value, '--yes']).exit_code != 0
    assert snapshot(home) == before
    assert pull(deployment, '--yes').exit_code == 0
    first = records(home)[0].parent
    before = snapshot(home)
    result = CliRunner().invoke(main, ['instructions', 'restore', first.name, '--replace', '--yes'])
    assert result.exit_code != 0 and 'previous' in result.output
    assert snapshot(home) == before
    assert canonical.read_text() == '# Atlas v1\n'


@pytest.mark.parametrize('url', ['https://user:TOPSECRET@github.com/owner/repo',
                                'https://github.com/owner/repo?token=TOPSECRET',
                                'https://github.com/owner/repo#TOPSECRET',
                                'ssh://user:TOPSECRET@github.com/owner/repo',
                                'ssh://git@github.com/owner/repo?token=TOPSECRET'])
def test_url_credentials_and_queries_rejected_before_fetch(deployment, monkeypatch, url):
    def forbidden(*args):
        pytest.fail('invalid URL reached Git')
    monkeypatch.setattr(source, '_git', forbidden)
    result = pull(deployment, '--source', url, '--yes')
    assert result.exit_code == 1
    assert 'TOPSECRET' not in result.output


@pytest.mark.parametrize('phase', ['backup', 'swap'])
def test_failed_write_preserves_canonical_and_keeps_no_staging_file(deployment, monkeypatch, phase):
    home, _, canonical, _, _ = deployment
    canonical.parent.mkdir()
    canonical.write_text('unpublished local content\n')
    if phase == 'swap':
        def fail(*args):
            raise OSError('injected swap failure')
        monkeypatch.setattr(source.os, 'replace', fail)
    else:
        original = source.os.fsync
        calls = 0
        def fail(fd):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('injected backup failure')
            return original(fd)
        monkeypatch.setattr(source.os, 'fsync', fail)
    result = pull(deployment, '--replace', '--yes')
    assert result.exit_code == 1 and 'injected' in result.output
    assert canonical.read_text() == 'unpublished local content\n'
    assert not list(canonical.parent.glob('.AGENTS-*'))
    if phase == 'swap':
        assert (records(home)[0].parent / 'previous.md').read_text() == 'unpublished local content\n'


def test_canonical_change_after_preview_is_not_overwritten(deployment, monkeypatch):
    _, _, canonical, _, _ = deployment
    canonical.parent.mkdir()
    canonical.write_text('old\n')
    import importlib
    command_module = importlib.import_module('agent_toolkit_cli.commands.instructions.pull_cmd')
    def edit_during_prompt(*args, **kwargs):
        canonical.write_text('concurrent edit\n')
        return True
    monkeypatch.setattr(command_module.click, 'confirm', edit_during_prompt)
    result = pull(deployment, '--replace')
    assert result.exit_code == 1 and 'changed' in result.output
    assert canonical.read_text() == 'concurrent edit\n'


@pytest.mark.parametrize('component', ['root', 'history', 'deployment', 'backup'])
def test_symlink_storage_is_refused_without_writing_through_it(deployment, component, tmp_path):
    home, _, canonical, _, _ = deployment
    if component == 'root':
        foreign = tmp_path / 'external-root'
        foreign.mkdir()
        canonical.parent.symlink_to(foreign, target_is_directory=True)
        before = snapshot(home)
        assert pull(deployment, '--yes').exit_code == 1
        assert snapshot(home) == before and not list(foreign.iterdir())
        return
    canonical.parent.mkdir()
    canonical.write_text('original\n')
    assert pull(deployment, '--replace', '--yes').exit_code == 0
    directory = records(home)[0].parent
    path = {'history': directory.parent, 'deployment': directory,
            'backup': directory / 'previous.md'}[component]
    moved = path.with_name(path.name + '-retained')
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=moved.is_dir())
    before = snapshot(home)
    result = CliRunner().invoke(main, ['instructions', 'restore', directory.name, '--replace', '--yes'])
    assert result.exit_code == 1
    assert snapshot(home) == before


def test_restore_preview_and_corrupt_backup(deployment):
    home, _, canonical, _, _ = deployment
    canonical.parent.mkdir()
    canonical.write_text('original\n')
    assert pull(deployment, '--replace', '--yes').exit_code == 0
    directory = records(home)[0].parent
    before = snapshot(home)
    result = CliRunner().invoke(main, ['instructions', 'restore', directory.name, '--dry-run'])
    assert result.exit_code == 0 and 'original' in result.output
    assert snapshot(home) == before
    (directory / 'previous.md').write_text('tampered\n')
    before = snapshot(home)
    result = CliRunner().invoke(main, ['instructions', 'restore', directory.name, '--replace', '--yes'])
    assert result.exit_code == 1 and 'receipt' in result.output
    assert snapshot(home) == before


def test_default_pull_follows_latest_main_and_git_revert(deployment):
    home, repo, canonical, _, git = deployment
    args = ['instructions', 'pull', '--source', str(repo), '--host', 'atlas']
    (repo / 'agents-instructions/AGENTS.atlas.md').write_text('# Latest Atlas\n')
    git('add', '.')
    git('commit', '-m', 'update latest instructions')
    latest = git('rev-parse', 'main')
    result = CliRunner().invoke(main, [*args, '--yes'])
    assert result.exit_code == 0, result.output
    assert canonical.read_text() == '# Latest Atlas\n'
    receipt = json.loads(records(home)[0].read_text())
    assert receipt['ref'] == 'main' and receipt['commit'] == latest
    # Ordinary Git history provides rollback, without another release/tag.
    git('revert', '--no-edit', 'HEAD')
    reverted = git('rev-parse', 'main')
    result = CliRunner().invoke(main, [*args, '--replace', '--yes'])
    assert result.exit_code == 0, result.output
    assert canonical.read_text() == '# Atlas v1\n'
    assert reverted in result.output


@pytest.mark.parametrize('host', ['atlas', 'k2', 'hima'])
def test_export_repository_root_layout(deployment, host):
    home, repo, canonical, _, git = deployment
    nested = repo / f'agents-instructions/AGENTS.{host}.md'
    if nested.exists():
        git('rm', f'agents-instructions/AGENTS.{host}.md')
    body = f'# {host} exported instructions\n'
    (repo / f'AGENTS.{host}.md').write_text(body)
    git('add', '.')
    git('commit', '-m', 'export host file at repository root')
    result = CliRunner().invoke(main, ['instructions', 'pull', '--source', str(repo),
                                     '--host', host, '--yes'])
    assert result.exit_code == 0, result.output
    assert canonical.read_text() == body
    receipt = json.loads(records(home)[0].read_text())
    assert receipt['path'] == f'AGENTS.{host}.md'
    assert receipt['host'] == host
    assert receipt['ref'] == 'main'


def test_ambiguous_root_and_workspace_host_files_are_refused(deployment):
    home, repo, _, _, git = deployment
    (repo / 'AGENTS.atlas.md').write_text('# competing root copy\n')
    git('add', '.')
    git('commit', '-m', 'ambiguous layouts')
    before = snapshot(home)
    result = CliRunner().invoke(main, ['instructions', 'pull', '--source', str(repo),
                                     '--host', 'atlas', '--yes'])
    assert result.exit_code == 1 and 'ambiguous' in result.output
    assert snapshot(home) == before


def test_help_and_global_only_contract():
    for verb in ['pull', 'restore']:
        result = CliRunner().invoke(main, ['instructions', verb, '--help'])
        assert result.exit_code == 0 and 'global' in result.output
        assert '--dry-run' in result.output and '--replace' in result.output
        assert '--scope' not in result.output
