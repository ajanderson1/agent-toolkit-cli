"""#418 — agent implicit-scope banner (mirrors #413 for skill).

Covers `scope_and_roots`'s `implicit` 4-tuple, the `scope_banner` helper, and
the wiring into the agent read verbs (list/status/update/reset/push/doctor).
"""
from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli  # entrypoint symbol is `main`
from agent_toolkit_cli.commands.agent._common import scope_and_roots, scope_banner


# --- Task 1: scope_and_roots returns the implicit 4-tuple -------------------


def test_scope_and_roots_explicit_global_is_not_implicit():
    assert scope_and_roots(True, False, None) == ("global", Path.home(), None, False)


def test_scope_and_roots_explicit_project_is_not_implicit(tmp_path):
    assert scope_and_roots(False, True, tmp_path) == ("project", None, tmp_path, False)


def test_scope_and_roots_implicit_global_when_read_only_and_no_lock(tmp_path):
    # read_only + no agents-lock.json in cwd → global fallback, implicit=True
    assert scope_and_roots(False, False, tmp_path, read_only=True) == (
        "global",
        Path.home(),
        None,
        True,
    )


def test_scope_and_roots_implicit_project_when_lock_present(tmp_path):
    (tmp_path / "agents-lock.json").write_text("{}")
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
        scope="project", implicit=True, lock_path="/p/agents-lock.json", count=3
    )
    assert "Operating on project scope — /p/agents-lock.json (3 agents)." in r.stdout
    assert "Pass -g for the global library." in r.stdout


def test_banner_singular_noun():
    r = _run_banner(
        scope="project", implicit=True, lock_path="/p/agents-lock.json", count=1
    )
    assert "(1 agent)." in r.stdout


def test_banner_count_zero_still_prints():
    r = _run_banner(
        scope="project", implicit=True, lock_path="/p/agents-lock.json", count=0
    )
    assert "(0 agents)." in r.stdout


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


# --- Tasks 3 & 4: wiring into the read verbs --------------------------------


def _seed_project_lock(tmp_path: Path) -> None:
    """A minimal valid agents-lock.json with one entry, in tmp_path."""
    (tmp_path / "agents-lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "demo-agent": {
                        "source": "https://example.com/demo-agent",
                        "sourceType": "git",
                        "ref": "main",
                    }
                },
            }
        )
    )


def test_agent_list_human_banner_on_stdout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["agent", "list"])
    assert r.exit_code == 0
    assert "Operating on project scope" in r.stdout
    assert "(1 agent)." in r.stdout


def test_agent_list_json_banner_on_stderr_stdout_is_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["agent", "list", "--json"])
    assert r.exit_code == 0
    json.loads(r.stdout)  # stdout parses clean
    assert "Operating on project scope" in r.stderr


def test_agent_list_no_banner_when_global_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no agents-lock.json → global fallback
    r = CliRunner().invoke(cli, ["agent", "list"])
    assert "Operating on project scope" not in r.stdout
    assert "Operating on project scope" not in r.stderr


# reset (and push) iterate over targets; reset rejects a bare invocation with a
# UsageError that fires BEFORE scope_and_roots, so it must be given a slug.
_ARGV = {
    "status": ["agent", "status"],
    "update": ["agent", "update"],
    "reset": ["agent", "reset", "demo-agent"],
    "push": ["agent", "push"],
    "doctor": ["agent", "doctor"],
}


@pytest.mark.parametrize("verb", ["status", "update", "reset", "push", "doctor"])
def test_agent_read_verb_banner_on_stdout(verb, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, _ARGV[verb])
    # Banner is advisory; the verb may still exit non-zero for other reasons.
    assert "Operating on project scope" in r.stdout
