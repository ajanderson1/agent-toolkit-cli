"""#420 — pi-extension implicit-scope banner (mirrors #413 for skill).

Covers `scope_and_roots`'s `implicit` 4-tuple, the `scope_banner` helper, and
the wiring into the pi read verbs (list/status/update/reset/push/doctor). pi
deltas: list/status/doctor are inventory/diagnose-based (introduced lock read
for the count), list has --json (banner → stderr) while status does not, and
the count is len(lock.skills) (pi read_lock returns a LockFile).
"""
from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli  # entrypoint symbol is `main`
from agent_toolkit_cli.commands.pi_extension._common import (
    scope_and_roots,
    scope_banner,
)
from agent_toolkit_cli.pi_extension_lock import LockEntry, LockFile, write_lock


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
    (tmp_path / "pi-extensions-lock.json").write_text('{"version": 1, "skills": {}}')
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
        scope="project", implicit=True, lock_path="/p/pi-extensions-lock.json", count=3
    )
    assert (
        "Operating on project scope — /p/pi-extensions-lock.json (3 pi extensions)."
        in r.stdout
    )
    assert "Pass -g for the global library." in r.stdout


def test_banner_singular_noun():
    r = _run_banner(
        scope="project", implicit=True, lock_path="/p/pi-extensions-lock.json", count=1
    )
    assert "(1 pi extension)." in r.stdout


def test_banner_count_zero_still_prints():
    r = _run_banner(
        scope="project", implicit=True, lock_path="/p/pi-extensions-lock.json", count=0
    )
    assert "(0 pi extensions)." in r.stdout


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
    """A minimal valid pi-extensions-lock.json with one entry, in tmp_path."""
    write_lock(
        tmp_path / "pi-extensions-lock.json",
        LockFile(
            version=1,
            skills={
                "demo-ext": LockEntry(
                    source="https://example.com/demo-ext",
                    source_type="git",
                    ref="main",
                ),
            },
        ),
    )


def _isolate_home_and_chdir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)


def test_pi_list_human_banner_on_stdout(tmp_path, monkeypatch):
    _isolate_home_and_chdir(tmp_path, monkeypatch)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["pi-extension", "list"])
    assert "Operating on project scope" in r.stdout
    assert "(1 pi extension)." in r.stdout


def test_pi_list_json_banner_on_stderr_stdout_is_json(tmp_path, monkeypatch):
    _isolate_home_and_chdir(tmp_path, monkeypatch)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["pi-extension", "list", "--json"])
    json.loads(r.stdout)  # stdout parses clean
    assert "Operating on project scope" in r.stderr


def test_pi_status_banner_on_stdout(tmp_path, monkeypatch):
    _isolate_home_and_chdir(tmp_path, monkeypatch)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, ["pi-extension", "status"])
    assert "Operating on project scope" in r.stdout


def test_pi_list_no_banner_when_global_fallback(tmp_path, monkeypatch):
    # Isolate HOME: the global path reads ~/.agent-toolkit via build_inventory.
    _isolate_home_and_chdir(tmp_path, monkeypatch)  # no lock in cwd → global
    r = CliRunner().invoke(cli, ["pi-extension", "list"])
    assert "Operating on project scope" not in r.stdout
    assert "Operating on project scope" not in r.stderr


# reset rejects a bare invocation with UsageError BEFORE scope_and_roots, so it
# must be given a slug (the seeded "demo-ext"). update/push reach the banner over
# the no-slug one-entry lock; doctor introduces its own read.
_ARGV = {
    "update": ["pi-extension", "update"],
    "reset": ["pi-extension", "reset", "demo-ext"],
    "push": ["pi-extension", "push"],
    "doctor": ["pi-extension", "doctor"],
}


@pytest.mark.parametrize("verb", ["update", "reset", "push", "doctor"])
def test_pi_read_verb_banner_on_stdout(verb, tmp_path, monkeypatch):
    _isolate_home_and_chdir(tmp_path, monkeypatch)
    _seed_project_lock(tmp_path)
    r = CliRunner().invoke(cli, _ARGV[verb])
    # Banner is advisory; the verb may exit non-zero for other reasons.
    assert "Operating on project scope" in r.stdout
