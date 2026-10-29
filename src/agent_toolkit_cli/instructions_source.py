"""Explicit global content deployment; independent of Instructions exposure."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from agent_toolkit_cli.instructions_paths import global_canonical_agents_md
from agent_toolkit_cli.skill_source import SourceParseError, parse_source, sanitize_ref

MAX_BLOB = 256 * 1024
MAX_LOCAL = 1024 * 1024


class DeploymentError(ValueError):
    """Unsafe source, destination or deployment request."""


@dataclass(frozen=True)
class Candidate:
    content: bytes
    provenance: dict


@dataclass(frozen=True)
class Current:
    content: bytes | None
    identity: tuple | None


def _git(repo: Path, *args: str) -> bytes:
    # No checkout, hooks, submodules or inherited Git directory/config overrides.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['GIT_SSH_COMMAND'] = os.environ.get('GIT_SSH_COMMAND', 'ssh -o BatchMode=yes')
    proc = subprocess.run(
        ['git', '-c', 'protocol.ext.allow=never', '-C', str(repo), *args],
        env=env, capture_output=True, timeout=120,
    )
    if proc.returncode:
        # Do not echo remote diagnostics, which can contain credential-bearing URLs.
        raise DeploymentError('Git source operation failed; check repository access, ref and Git authentication')
    return proc.stdout


def fetch(source: str, host: str, ref: str) -> Candidate:
    host = host.lower()
    if len(host) > 253 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                                  for label in host.split('.')):
        raise DeploymentError('host must be an explicit DNS-style hostname, not a path')
    sanitize_ref(ref)
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]*', ref):
        raise DeploymentError('ref must be a branch, tag or full commit SHA, not a refspec or revision expression')
    if any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in source):
        raise DeploymentError('source contains control characters')
    raw_url = urlparse(source)
    if raw_url.scheme in ('https', 'ssh') and (raw_url.password or raw_url.query or raw_url.fragment
                                              or (raw_url.scheme == 'https' and raw_url.username)):
        raise DeploymentError('use a Git credential helper, not credentials/query parameters in the source URL')
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise DeploymentError('invalid repository source; use a repository-root URL or explicit local path') from exc
    url = parsed.url
    parts = urlparse(url)
    if parsed.ref or parsed.subpath or parsed.skill_name:
        raise DeploymentError('source must name a repository root; supply the revision with --ref')
    if parsed.type != 'local' and not (url.startswith(('https://', 'ssh://', 'git@'))):
        raise DeploymentError('source must use HTTPS, SSH or an explicit local repository path')
    if parts.scheme in ('https', 'ssh') and (parts.password or parts.query or parts.fragment
                                           or (parts.scheme == 'https' and parts.username)):
        raise DeploymentError('use a Git credential helper, not credentials/query parameters in the source URL')
    paths = [f'AGENTS.{host}.md', f'agents-instructions/AGENTS.{host}.md']
    with tempfile.TemporaryDirectory(prefix='atc-instructions-source-') as directory:
        repo = Path(directory)
        _git(repo, 'init', '--bare')
        _git(repo, 'remote', 'add', 'origin', url)
        _git(repo, 'config', 'remote.origin.promisor', 'true')
        _git(repo, 'config', 'remote.origin.partialclonefilter', 'blob:none')
        _git(repo, 'fetch', '--depth=1', '--no-tags', '--no-recurse-submodules',
             '--filter=blob:none', 'origin', ref)
        commit = _git(repo, 'rev-parse', 'FETCH_HEAD^{commit}').decode().strip()
        entries = [entry for entry in _git(repo, 'ls-tree', '-z', commit, '--', *paths).split(b'\0') if entry]
        if len(entries) > 1:
            raise DeploymentError('ambiguous host instructions: both repository-root and workspace paths exist; retain one source')
        if not entries:
            raise DeploymentError(f'host instructions must exist as a regular committed file: {paths[0]} or {paths[1]}')
        header, raw_path = entries[0].split(b'\t', 1)
        entry = header.split()
        path = raw_path.decode('ascii')
        if len(entry) != 3 or entry[0] not in (b'100644', b'100755') or entry[1] != b'blob':
            raise DeploymentError(f'{path} must exist as a regular committed file')
        blob = entry[2].decode('ascii')
        if int(_git(repo, 'cat-file', '-s', blob)) > MAX_BLOB:
            raise DeploymentError('instruction source exceeds 256 KiB')
        content = _git(repo, 'cat-file', 'blob', blob)
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise DeploymentError('instruction source must be UTF-8 text') from exc
    if not text.strip() or any((ord(c) < 32 and c not in '\n\r\t') or 127 <= ord(c) <= 159 for c in text):
        raise DeploymentError('instruction source is empty or contains control characters')
    return Candidate(content, {'operation': 'pull', 'source': url, 'host': host,
                               'ref': ref, 'commit': commit, 'path': path})


def _directory(path: Path, *, create: bool = False) -> None:
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise DeploymentError(f'refusing non-directory or symlink directory: {path}')


def read_regular(path: Path) -> Current:
    """Read a bounded regular file without following the final symlink."""
    if os.name != 'posix':
        raise DeploymentError('instruction content deployment currently requires macOS/Linux (POSIX filesystem guards)')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return Current(None, None)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_LOCAL:
            raise DeploymentError(f'refusing nonregular file or file over 1 MiB: {path}')
        content = stream.read(MAX_LOCAL + 1)
        if len(content) > MAX_LOCAL:
            raise DeploymentError(f'file grew beyond 1 MiB: {path}')
        identity = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size)
    return Current(content, identity)


def current() -> Current:
    canonical = global_canonical_agents_md()
    _directory(canonical.parent)
    return read_regular(canonical)


def restore_candidate(deployment: str) -> Candidate:
    if not re.fullmatch(r'deploy-[A-Za-z0-9_-]+', deployment):
        raise DeploymentError('supply a deployment ID, not a filesystem path')
    root = global_canonical_agents_md().parent
    _directory(root)
    history = root / 'instructions-deployments'
    _directory(history)
    directory = history / deployment
    _directory(directory)
    previous = read_regular(directory / 'previous.md').content
    receipt = read_regular(directory / 'deployment.json').content
    if previous is None or receipt is None:
        raise DeploymentError('deployment has no previous content to restore')
    record = json.loads(receipt)
    if not isinstance(record, dict) or record.get('previous_sha256') != hashlib.sha256(previous).hexdigest():
        raise DeploymentError('previous content does not match the deployment receipt')
    return Candidate(previous, {'operation': 'restore', 'restored_from': deployment})


def deploy(candidate: Candidate, expected: Current) -> Path:
    """Back up first, then atomically replace only the canonical directory entry.

    Receipts describe prepared deployments, including attempts whose final swap
    failed. Their content hash, not their time/order, establishes a content match.
    The directory flock only serializes this deployment API, not arbitrary editors.
    """
    import fcntl

    canonical = global_canonical_agents_md()
    root = canonical.parent
    _directory(root, create=True)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(root_fd, fcntl.LOCK_EX)
        if current() != expected:
            raise DeploymentError('canonical changed since preview; inspect and retry')
        history = root / 'instructions-deployments'
        _directory(history, create=True)
        directory = Path(tempfile.mkdtemp(prefix='deploy-', dir=history))
        record = dict(candidate.provenance, sha256=hashlib.sha256(candidate.content).hexdigest(),
                      previous_sha256=(hashlib.sha256(expected.content).hexdigest()
                                       if expected.content is not None else None),
                      prepared_at=datetime.now(timezone.utc).isoformat())
        files = {'AGENTS.md': candidate.content,
                 'deployment.json': (json.dumps(record, indent=2) + '\n').encode()}
        if expected.content is not None:
            files['previous.md'] = expected.content
        for name, content in files.items():
            with (directory / name).open('xb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        fd, staging = tempfile.mkstemp(prefix='.AGENTS-', dir=root)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(candidate.content)
                stream.flush()
                os.fsync(stream.fileno())
            if current() != expected:
                raise DeploymentError('canonical changed during staging; backup retained, inspect and retry')
            os.replace(staging, canonical)
        finally:
            Path(staging).unlink(missing_ok=True)
        return directory
    finally:
        os.close(root_fd)
