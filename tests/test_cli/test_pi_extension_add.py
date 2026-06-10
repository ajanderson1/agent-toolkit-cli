"""`pi-extension add` core tests (Task 3).

Lock-after-clone, idempotency, npm record, store-owned clone.
"""
import pytest

from agent_toolkit_cli import pi_extension_add as pea
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import read_lock


def test_add_npm_records_registry_entry_no_clone(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source="npm:@scope/rpiv-i18n", slug=None, env={})
    lock = read_lock(pep.library_lock_path(env={}))
    entry = lock.skills["@scope/rpiv-i18n"]
    assert entry.source == "npm:@scope/rpiv-i18n"
    assert entry.source_type == "npm"
    assert entry.pi_extension_path is None  # not stored
    # No store dir created.
    assert not pep.library_pi_extension_path("@scope/rpiv-i18n", env={}).exists()


def test_add_store_owned_clones_and_records(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    # git_sandbox.upstream is a bare repo seeded with SKILL.md; reuse as a
    # generic git source. Add as a store-owned extension named "demo".
    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)
    canonical = pep.library_pi_extension_path("demo", env={})
    assert canonical.exists()
    lock = read_lock(pep.library_lock_path(env={}))
    entry = lock.skills["demo"]
    assert entry.source_type != "npm"
    assert entry.pi_extension_path == "demo"


def test_add_lock_written_only_after_clone(tmp_path, monkeypatch):
    # A clone failure (bad source) must NOT leave a lock entry behind (#283).
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(Exception):  # noqa: BLE001
        pea.add(source="/nonexistent/does-not-exist-xyz", slug="ghost", env={})
    lock = read_lock(pep.library_lock_path(env={}))
    assert "ghost" not in lock.skills


def test_add_npm_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source="npm:foo", slug=None, env={})
    pea.add(source="npm:foo", slug=None, env={})
    lock = read_lock(pep.library_lock_path(env={}))
    assert list(lock.skills) == ["foo"]


@pytest.mark.parametrize("ref,expected", [
    ("22d0c764cd6c10ed06a7877e55a606d3435f1ec5", True),   # full SHA
    ("22d0c76", True),                                     # abbreviated SHA
    ("deadbeef", True),                                    # 8-hex
    ("main", False),                                       # branch
    ("v1.2.3", False),                                     # tag
    ("feature/foo", False),                                # slashed branch
    (None, False),                                         # no ref
    ("22d0c7", False),                                     # 6 hex chars: below git's 7-char floor
    ("g2d0c764", False),                                   # non-hex char
    ("DEADBEEF", False),                                   # uppercase: git SHAs print lowercase
])
def test_looks_like_sha(ref, expected):
    assert pea.looks_like_sha(ref) is expected


import subprocess


def _push_second_commit(git_sandbox) -> tuple[str, str]:
    """Create a second upstream commit; return (first_sha, second_sha)."""
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(git_sandbox.clone), *args],
            check=True, env=git_sandbox.env, capture_output=True, text=True,
        ).stdout.strip()

    first_sha = git("rev-parse", "HEAD")
    (git_sandbox.clone / "EXTRA.md").write_text("second\n")
    git("add", "-A")
    git("commit", "-m", "second")
    git("push", "origin", "main")
    second_sha = git("rev-parse", "HEAD")
    return first_sha, second_sha


def test_add_sha_pinned_lands_on_pin(tmp_path, monkeypatch, git_sandbox):
    """A /tree/<sha> source must land the store copy on the pinned commit,
    not the branch HEAD (#330). Same parsed.ref shape as owner/repo@<sha>."""
    monkeypatch.setenv("HOME", str(tmp_path))
    first_sha, second_sha = _push_second_commit(git_sandbox)

    pea.add(
        source=f"file://{git_sandbox.upstream}/tree/{first_sha}",
        slug="pinned", env=git_sandbox.env,
    )

    canonical = pep.library_pi_extension_path("pinned", env={})
    head = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head == first_sha != second_sha
    # Worktree reflects the pinned commit, not HEAD.
    assert not (canonical / "EXTRA.md").exists()
    # Lock records the pin; upstream_sha is None (no origin/<sha> remote ref).
    entry = read_lock(pep.library_lock_path(env={})).skills["pinned"]
    assert entry.ref == first_sha
    assert entry.local_sha == first_sha
    assert entry.upstream_sha is None


def test_add_abbreviated_sha_pin_expands(tmp_path, monkeypatch, git_sandbox):
    """A 7-char pin must land on the full commit: `git fetch origin <short>`
    always fails (best-effort), and checkout resolves it locally (#330)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    first_sha, second_sha = _push_second_commit(git_sandbox)

    pea.add(
        source=f"file://{git_sandbox.upstream}/tree/{first_sha[:7]}",
        slug="shortpin", env=git_sandbox.env,
    )

    canonical = pep.library_pi_extension_path("shortpin", env={})
    head = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head == first_sha != second_sha
    assert not (canonical / "EXTRA.md").exists()
