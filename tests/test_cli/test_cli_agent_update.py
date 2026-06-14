"""CLI tests for `agent update` (#423 / AC1).

Mirrors tests/test_cli/test_cli_pi_extension_lifecycle.py update cases —
`agent update` is documented as mirroring pi-extension update_cmd.

The shared git_sandbox seeds SKILL.md upstream, but `agent add --slug demo`
needs a demo.md content file in the source, so these tests build a dedicated
upstream seeded with demo.md.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.agent_lock import LockEntry, add_entry, read_lock, write_lock
from agent_toolkit_cli.agent_paths import library_agent_path, library_lock_path
from agent_toolkit_cli.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_upstream(tmp_path: Path, env: dict, slug: str = "demo") -> Path:
    """A bare upstream seeded with <slug>.md so `agent add --slug` accepts it."""
    upstream = tmp_path / f"{slug}-upstream.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(upstream)],
        check=True, env=env, capture_output=True,
    )
    seed = tmp_path / f"{slug}-seed"
    seed.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(seed)],
        check=True, env=env, capture_output=True,
    )
    (seed / f"{slug}.md").write_text(
        f"---\nname: {slug}\ndescription: A test agent.\n---\n\nBody.\n"
    )
    for args in (
        ["add", "-A"],
        ["commit", "-m", "seed"],
        ["remote", "add", "origin", str(upstream)],
        ["push", "origin", "main"],
    ):
        subprocess.run(
            ["git", "-C", str(seed), *args],
            check=True, env=env, capture_output=True,
        )
    return upstream


def _advance_remote(upstream: Path, env: dict, *, slug: str = "demo",
                    body: str = "updated\n") -> None:
    """Push a new commit to the upstream bare repo."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        subprocess.run(
            ["git", "clone", str(upstream), str(work)],
            check=True, capture_output=True, env=env,
        )
        (work / f"{slug}.md").write_text(body)
        for args in (
            ["add", "-A"],
            ["commit", "-m", "upstream update"],
            ["push", "origin", "main"],
        ):
            subprocess.run(
                ["git", "-C", str(work), *args],
                check=True, capture_output=True, env=env,
            )


def _head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_agent_update_pulls_upstream_changes(tmp_path, monkeypatch, git_sandbox):
    """Happy path: agent update fetches + merges and advances HEAD + lock SHA."""
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))

    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)
    r = CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    canonical = library_agent_path("demo")
    _advance_remote(upstream, git_sandbox.env)
    sha_before = _head(canonical)

    r = CliRunner().invoke(main, ["agent", "update", "demo", "-g"])
    assert r.exit_code == 0, r.output
    sha_after = _head(canonical)
    assert sha_before != sha_after, "update should advance HEAD"

    lock = read_lock(library_lock_path())
    assert lock.skills["demo"].local_sha == sha_after


def test_agent_update_unknown_slug_reports_error(tmp_path, monkeypatch, git_sandbox):
    """A named slug not in the lock => '{slug}: not in lock' + exit 1.

    Seed one real entry first so the lock is non-empty — the 'not in lock'
    branch fires (rather than the empty-lock no-op).
    """
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)
    CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])

    r = CliRunner().invoke(main, ["agent", "update", "nope", "-g"])
    assert r.exit_code != 0
    assert "nope: not in lock" in r.output


def test_agent_update_no_lock_is_silent_noop(tmp_path, monkeypatch):
    """With no lock at all, read_lock swallows FileNotFoundError → empty lock
    → targets=() → loop runs zero times → exit 0 with empty output.
    The 'no agents lock found' branch in update_cmd.py is dead code
    (read_lock never raises FileNotFoundError). Assert the REAL behaviour.
    """
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)
    r = CliRunner().invoke(main, ["agent", "update", "-g"])
    assert r.exit_code == 0, r.output
    assert r.output.strip() == "", f"expected empty output, got: {r.output!r}"


def test_agent_update_no_args_updates_all(tmp_path, monkeypatch, git_sandbox):
    """No slug argument => update all agents in the lock."""
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)
    CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])
    _advance_remote(upstream, git_sandbox.env)
    r = CliRunner().invoke(main, ["agent", "update", "-g"])  # no slug => all
    assert r.exit_code == 0, r.output
    assert "demo: updated" in r.output


def test_agent_update_non_git_canonical_reports_error(tmp_path, monkeypatch):
    """A lock entry whose canonical has no .git/ cannot update => message + exit 1.

    Seed directly at library_agent_path("plain") — the exact path update_cmd
    reads. This reaches the `no .git/` branch (exit 1, specific message).
    """
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)

    # Seed a NON-git canonical at the path the command reads + a lock entry for it.
    canonical = library_agent_path("plain")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "plain.md").write_text("---\nname: plain\ndescription: x\n---\nB\n")

    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    write_lock(
        lock_path,
        add_entry(lock, "plain", LockEntry(
            source="https://github.com/test/plain",
            source_type="github",
            agent_path="plain.md",
        )),
    )

    r = CliRunner().invoke(main, ["agent", "update", "plain", "-g"])
    assert r.exit_code != 0
    assert "no .git" in r.output


# ---------------------------------------------------------------------------
# Project-scope variants (G3 / AC3)
# ---------------------------------------------------------------------------


def test_agent_update_project_scope_pulls_upstream(tmp_path, monkeypatch, git_sandbox):
    """agent update -p fetches + merges at project scope."""
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)

    project = tmp_path / "proj"
    project.mkdir()

    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)

    # `agent add` is global-only; add globally then install into project scope.
    r = CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    # Install into project scope to populate the project lock.
    r = CliRunner().invoke(
        main, ["--project", str(project),
               "agent", "install", "demo", "-p", "--harnesses", "claude-code"],
    )
    assert r.exit_code == 0, r.output

    # Advance the upstream so there's something to pull.
    _advance_remote(upstream, git_sandbox.env)

    r = CliRunner().invoke(
        main, ["--project", str(project), "agent", "update", "demo", "-p"],
    )
    assert r.exit_code == 0, r.output
    assert "demo: updated" in r.output


def test_agent_reset_project_scope_unknown_slug(tmp_path, monkeypatch, git_sandbox):
    """agent reset -p with unknown slug => 'not in lock' error."""
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)

    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)

    # Add + install into project so the project lock exists.
    CliRunner().invoke(main, ["--project", str(project), "agent", "add", str(upstream), "--slug", "demo"])

    r = CliRunner().invoke(main, ["--project", str(project), "agent", "reset", "ghost", "-p"])
    assert r.exit_code != 0
    assert "ghost: not in lock" in r.output