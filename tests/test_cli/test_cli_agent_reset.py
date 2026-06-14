"""CLI tests for `agent reset` — behavioral depth (#423 / AC0b).

The --help smoke already exists in test_cli_agent_group.py; this file adds a
happy-path behavioral assertion: `agent reset <slug>` fetches upstream and
force-syncs the canonical, updating the lock SHA.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import library_agent_path, library_lock_path
from agent_toolkit_cli.cli import main


def _make_agent_upstream(tmp_path: Path, env: dict, slug: str = "demo") -> Path:
    """Bare upstream seeded with <slug>.md so `agent add --slug` accepts it."""
    upstream = tmp_path / f"{slug}-upstream.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(upstream)],
        check=True,
        env=env,
        capture_output=True,
    )
    seed = tmp_path / f"{slug}-seed"
    seed.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(seed)],
        check=True,
        env=env,
        capture_output=True,
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
            check=True,
            env=env,
            capture_output=True,
        )
    return upstream


def _advance_remote(
    upstream: Path, env: dict, *, slug: str = "demo", body: str = "reset-body\n"
) -> None:
    """Push a new commit to upstream so reset has something to sync to."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        subprocess.run(
            ["git", "clone", str(upstream), str(work)],
            check=True,
            capture_output=True,
            env=env,
        )
        (work / f"{slug}.md").write_text(body)
        for args in (
            ["add", "-A"],
            ["commit", "-m", "upstream advance"],
            ["push", "origin", "main"],
        ):
            subprocess.run(
                ["git", "-C", str(work), *args],
                check=True,
                capture_output=True,
                env=env,
            )


def _head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_agent_reset_force_syncs_to_upstream(tmp_path, monkeypatch, git_sandbox):
    """agent reset <slug> fetches + reset --hard and updates the lock SHA."""
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)

    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)
    r = CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    canonical = library_agent_path("demo")

    # Make a local commit so the canonical diverges from upstream.
    (canonical / "demo.md").write_text("local edit\n")
    subprocess.run(
        ["git", "-C", str(canonical), "add", "-A"],
        check=True,
        env=git_sandbox.env,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(canonical), "commit", "-m", "local diverge"],
        check=True,
        env=git_sandbox.env,
        capture_output=True,
    )

    # Also advance remote so reset --hard has something to sync.
    _advance_remote(upstream, git_sandbox.env)

    sha_before = _head(canonical)
    r = CliRunner().invoke(main, ["agent", "reset", "demo", "-g", "--force"])
    assert r.exit_code == 0, r.output
    sha_after = _head(canonical)

    # reset --hard to upstream HEAD; local commit is gone.
    assert sha_before != sha_after, "reset should move HEAD"
    assert "demo: reset to" in r.output

    lock = read_lock(library_lock_path())
    assert lock.skills["demo"].local_sha == sha_after


def test_agent_reset_unknown_slug_reports_error(tmp_path, monkeypatch, git_sandbox):
    """Resetting a slug not in the lock => '{slug}: not in lock' + exit 1."""
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))

    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)
    CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])

    r = CliRunner().invoke(main, ["agent", "reset", "ghost", "-g"])
    assert r.exit_code != 0
    assert "ghost: not in lock" in r.output
