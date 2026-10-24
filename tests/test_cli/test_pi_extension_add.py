"""`pi-extension add` core tests (Task 3).

Lock-after-clone, idempotency, npm record, store-owned clone.
"""
import json
import subprocess

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main

from agent_toolkit_cli import pi_extension_add as pea
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import read_lock
from agent_toolkit_tui.pi_extension_state import build_pi_rows


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


def test_add_bad_sha_fails_loud_no_orphans(tmp_path, monkeypatch, git_sandbox):
    """A pin absent from the remote must raise (fail-loud, NOT silently stay
    at HEAD), write no lock entry (#283), and leave no store dir (#313)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bogus = "0" * 40  # 40-hex, classified as SHA, exists nowhere

    with pytest.raises(Exception):  # GitError from fetch_ref
        pea.add(
            source=f"file://{git_sandbox.upstream}/tree/{bogus}",
            slug="ghost-pin", env=git_sandbox.env,
        )

    assert "ghost-pin" not in read_lock(pep.library_lock_path(env={})).skills
    assert not pep.library_pi_extension_path("ghost-pin", env={}).exists()


def test_add_heals_half_dir(tmp_path, monkeypatch, git_sandbox):
    """#347: a non-repo half-dir at the canonical path is rmtree'd and the
    source re-cloned — idempotent success only over a VALID repo."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = pep.library_pi_extension_path("demo", env={})
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")
    assert not (canonical / ".git").exists()

    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)

    assert (canonical / ".git").exists()
    assert not (canonical / "JUNK.md").exists()
    lock = read_lock(pep.library_lock_path(env={}))
    assert lock.skills["demo"].pi_extension_path == "demo"


def test_add_heals_empty_dir(tmp_path, monkeypatch, git_sandbox):
    """#347: an EMPTY canonical dir is also not-a-repo → healed, not trusted."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = pep.library_pi_extension_path("demo", env={})
    canonical.mkdir(parents=True)

    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)

    assert (canonical / ".git").exists()


def test_add_idempotent_over_valid_repo(tmp_path, monkeypatch, git_sandbox):
    """#347 regression: a second add over a VALID store copy is a no-op
    success (does NOT rmtree the repo)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)
    canonical = pep.library_pi_extension_path("demo", env={})
    (canonical / "MARKER.md").write_text("survives\n")

    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)

    assert (canonical / "MARKER.md").exists()
    assert read_lock(pep.library_lock_path(env={})).skills["demo"].pi_extension_path == "demo"


def test_add_refuses_source_mismatch_over_valid_repo(tmp_path, monkeypatch, git_sandbox):
    """#347 regression: a valid repo with a different source still REFUSES
    (is NOT silently re-cloned), and is left intact."""
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)
    canonical = pep.library_pi_extension_path("demo", env={})
    (canonical / "MARKER.md").write_text("survives\n")

    with pytest.raises(pea.AddError, match="different source"):
        pea.add(source="other/different-repo", slug="demo", env=git_sandbox.env)
    assert (canonical / "MARKER.md").exists()


@pytest.mark.parametrize("origin", [None, "https", "ssh"])
def test_add_registers_matching_untracked_checkout(tmp_path, monkeypatch, git_sandbox, origin):
    """An orphan checkout must become visible without recloning or activating it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = pep.library_pi_extension_path("demo", env={})
    pea.skill_git.clone(str(git_sandbox.upstream), canonical, ref=None, env=git_sandbox.env)
    source = str(git_sandbox.upstream)
    if origin is not None:
        remote = {
            "https": "https://github.com/obra/superpowers.git",
            "ssh": "git@github.com:obra/superpowers.git",
        }[origin]
        subprocess.run(
            ["git", "-C", str(canonical), "remote", "set-url", "origin", remote],
            check=True, env=git_sandbox.env, capture_output=True,
        )
        source = "https://github.com/obra/superpowers/tree/main"
    marker = canonical / "MARKER.md"
    marker.write_text("local work\n")
    before_sha = pea.skill_git.head_sha(canonical, env=git_sandbox.env)

    result = CliRunner().invoke(main, ["pi-extensions", "add", source, "--slug", "demo"])

    assert result.exit_code == 0, result.output
    entry = read_lock(pep.library_lock_path(env={})).skills["demo"]
    assert entry.source == ("obra/superpowers" if origin else source)
    assert entry.pi_extension_path == "demo"
    assert entry.local_sha == before_sha
    assert marker.read_text() == "local work\n"
    listing = CliRunner().invoke(main, ["pi-extensions", "list", "-g", "--json"])
    assert listing.exit_code == 0, listing.output
    row = next(row for row in json.loads(listing.output) if row["slug"] == "demo")
    assert row["origin"] == "store-owned"
    assert row["globalLoaded"] is False
    assert row["projectLoaded"] is False
    assert not (tmp_path / ".pi" / "agent" / "extensions" / "demo").exists()
    tui_row = next(row for row in build_pi_rows(home=tmp_path) if row.slug == "demo")
    assert tui_row.origin == "store-owned"
    assert tui_row.global_cell.global_loaded is False
    assert tui_row.project_cell.project_loaded is False


@pytest.mark.parametrize("origin", ["different", "missing"])
def test_add_refuses_unverified_untracked_checkout(tmp_path, monkeypatch, git_sandbox, origin):
    """No lock entry means origin must prove ownership; refusal preserves all data."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = pep.library_pi_extension_path("demo", env={})
    pea.skill_git.clone(str(git_sandbox.upstream), canonical, ref=None, env=git_sandbox.env)
    args = (
        ["set-url", "origin", "https://github.com/other/repo.git"]
        if origin == "different" else ["remove", "origin"]
    )
    subprocess.run(
        ["git", "-C", str(canonical), "remote", *args],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    marker = canonical / "MARKER.md"
    marker.write_text("local work\n")
    before_sha = pea.skill_git.head_sha(canonical, env=git_sandbox.env)

    result = CliRunner().invoke(
        main, ["pi-extensions", "add", str(git_sandbox.upstream), "--slug", "demo"]
    )

    assert result.exit_code != 0
    assert "origin" in result.output
    assert "refusing" in result.output.lower()
    assert marker.read_text() == "local work\n"
    assert pea.skill_git.head_sha(canonical, env=git_sandbox.env) == before_sha
    assert not pep.library_lock_path(env={}).exists()


@pytest.mark.parametrize("source", [
    "https://github.com/obra/superpowers/tree/main/.pi/extensions",
    "obra/superpowers/.pi/extensions",
])
def test_add_rejects_subpath_without_touching_existing_checkout(tmp_path, monkeypatch, git_sandbox, source):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = pep.library_pi_extension_path("superpowers", env={})
    pea.skill_git.clone(str(git_sandbox.upstream), canonical, ref=None, env=git_sandbox.env)
    marker = canonical / "MARKER.md"
    marker.write_text("local work\n")

    result = CliRunner().invoke(main, ["pi-extensions", "add", source])

    assert result.exit_code != 0
    assert "subdirector" in result.output.lower()
    assert ".pi/extensions" in result.output
    assert marker.read_text() == "local work\n"
    assert not pep.library_lock_path(env={}).exists()


def test_add_rejects_subpath_before_clone(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, [
        "pi-extensions", "add",
        f"file://{git_sandbox.upstream}/tree/main/.pi/extensions", "--slug", "demo",
    ])

    assert result.exit_code != 0
    assert "subdirector" in result.output.lower()
    assert not pep.library_pi_extension_path("demo", env={}).exists()
    assert not pep.library_lock_path(env={}).exists()
