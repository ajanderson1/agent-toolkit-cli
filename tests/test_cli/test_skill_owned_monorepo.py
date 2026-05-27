"""Owned monorepo: add records writable (no readOnly); --owned forces it."""
import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli.skill_paths import library_lock_path

from tests.conftest import scrub_git_env

FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _setup_parent(tmp_path, monkeypatch) -> tuple[str, Path]:
    parent = tmp_path / "parent"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent)], check=True)
    env = scrub_git_env()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return f"file://{parent}", parent


def _lock() -> dict:
    return json.loads(library_lock_path().read_text())


def _add_owned(parent_url: str, skill: str = "mkdocs") -> None:
    r = CliRunner().invoke(
        cli, ["skill", "add", parent_url, "--skill", skill, "--owned"],
    )
    assert r.exit_code == 0, r.output


def test_add_owned_writes_entry_without_readonly(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    r = CliRunner().invoke(
        cli, ["skill", "add", parent_url, "--skill", "mkdocs", "--owned"],
    )
    assert r.exit_code == 0, r.output
    entry = _lock()["skills"]["mkdocs"]
    assert "readOnly" not in entry  # writers omit readOnly when False
    assert entry["parentUrl"] == parent_url


def test_add_unowned_monorepo_keeps_readonly(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    r = CliRunner().invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r.exit_code == 0, r.output
    entry = _lock()["skills"]["mkdocs"]
    assert entry.get("readOnly") is True  # local owner is not owned


def test_owned_flag_on_single_skill_add_is_error(tmp_path, monkeypatch):
    _setup_parent(tmp_path, monkeypatch)
    # A single-skill add (no subpath/--skill) with --owned must fail loud.
    r = CliRunner().invoke(
        cli, ["skill", "add", "ajanderson1/journal-skill", "--owned"],
    )
    assert r.exit_code != 0
    assert "owned" in r.output.lower()
