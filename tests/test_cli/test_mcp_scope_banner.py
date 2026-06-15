"""#419 — mcp implicit-scope banner (mirrors #413 for skill, #418 for agent).

Covers `scope_and_roots`'s `implicit` 4-tuple, the `scope_banner` helper, and
the wiring into the mcp read verbs (list/status/doctor). mcp deltas: the lock is
a plain dict (count = len(lock)), there is no --json read verb (banner always
stdout), and `mcp update` is not wired (it does not use scope_and_roots).
"""
from __future__ import annotations

from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli  # entrypoint symbol is `main`
from agent_toolkit_cli.commands.mcp._common import scope_and_roots, scope_banner
from agent_toolkit_cli.mcp_lock import McpLockEntry, write_lock


# --- Task 1: scope_and_roots returns the implicit 4-tuple -------------------


def test_scope_and_roots_explicit_global_is_not_implicit():
    assert scope_and_roots(True, False, None) == ("global", Path.home(), None, False)


def test_scope_and_roots_explicit_project_is_not_implicit(tmp_path):
    assert scope_and_roots(False, True, tmp_path) == ("project", None, tmp_path, False)


def test_scope_and_roots_implicit_global_when_read_only_and_no_lock(tmp_path):
    assert scope_and_roots(False, False, tmp_path, read_only=True) == (
        "global",
        Path.home(),
        None,
        True,
    )


def test_scope_and_roots_implicit_project_when_lock_present(tmp_path):
    (tmp_path / "mcps-lock.json").write_text('{"mcps": {}}')
    assert scope_and_roots(False, False, tmp_path, read_only=True) == (
        "project",
        None,
        tmp_path,
        True,
    )


# --- Task 2: scope_banner helper --------------------------------------------


def _run_banner(**kwargs):
    @click.command()
    def cmd():
        scope_banner(**kwargs)

    return CliRunner().invoke(cmd, [])


def test_banner_prints_on_implicit_project_plural():
    r = _run_banner(
        scope="project", implicit=True, lock_path="/p/mcps-lock.json", count=3
    )
    assert "Operating on project scope — /p/mcps-lock.json (3 MCP servers)." in r.stdout
    assert "Pass -g for the global library." in r.stdout


def test_banner_singular_noun():
    r = _run_banner(
        scope="project", implicit=True, lock_path="/p/mcps-lock.json", count=1
    )
    assert "(1 MCP server)." in r.stdout


def test_banner_count_zero_still_prints():
    r = _run_banner(
        scope="project", implicit=True, lock_path="/p/mcps-lock.json", count=0
    )
    assert "(0 MCP servers)." in r.stdout


def test_banner_silent_on_implicit_global():
    r = _run_banner(scope="global", implicit=True, lock_path="/x", count=5)
    assert r.stdout == ""


def test_banner_silent_on_explicit_project():
    r = _run_banner(scope="project", implicit=False, lock_path="/x", count=5)
    assert r.stdout == ""


def test_banner_silent_on_explicit_global():
    r = _run_banner(scope="global", implicit=False, lock_path="/x", count=5)
    assert r.stdout == ""


def test_banner_err_routes_to_stderr():
    r = _run_banner(scope="project", implicit=True, lock_path="/p", count=2, err=True)
    assert r.stdout == ""
    assert "Operating on project scope" in r.stderr


# --- Task 3: wiring into the read verbs (list / status / doctor) ------------


def _seed_project_lock(tmp_path: Path) -> None:
    """A minimal valid mcps-lock.json with one tracked slug, in tmp_path."""
    write_lock(
        tmp_path / "mcps-lock.json",
        {"demo-mcp": [McpLockEntry(slug="demo-mcp", harness="claude-code", source="npx")]},
    )


@pytest.mark.parametrize("verb", ["list", "status", "doctor"])
def test_mcp_read_verb_banner_on_stdout(verb, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["mcp", verb])
    # Banner is advisory; the verb may exit non-zero for other reasons.
    assert "Operating on project scope" in r.stdout
    assert "(1 MCP server)." in r.stdout


def test_mcp_list_no_banner_when_global_fallback(tmp_path, monkeypatch):
    # Isolate HOME: the global-fallback path reads ~/.agent-toolkit via
    # library_root(Path.home()) and read_lock against the real global lock. A
    # malformed real global lock would raise (mcp read_lock is fail-loud), and
    # real global state makes the test environment-dependent. Point HOME at an
    # empty tmp dir so the global path reads nothing.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)  # no mcps-lock.json in cwd → global fallback
    r = CliRunner().invoke(cli, ["mcp", "list"])
    assert "Operating on project scope" not in r.stdout
    assert "Operating on project scope" not in r.stderr
