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
        # Accept pushes to the checked-out branch — the parent is a non-bare
        # file:// repo, so a --direct push to its `main` would otherwise hit
        # `denyCurrentBranch`. updateInstead keeps the worktree consistent.
        ["git", "config", "receive.denyCurrentBranch", "updateInstead"],
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


def test_owned_push_direct_commits_subpath_only(tmp_path, monkeypatch):
    """--direct push of an owned-monorepo skill commits ONLY that skill's
    subpath in the parent clone, even when a sibling subpath is dirty."""
    from agent_toolkit_cli.skill_paths import parent_clone_path

    parent_url, parent = _setup_parent(tmp_path, monkeypatch)
    _add_owned(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    sub = entry["skillPath"]  # e.g. "mkdocs"
    owner, repo = entry["source"].split("/", 1)
    clone = parent_clone_path(owner, repo, ref=entry.get("ref"), env=None)

    # Dirty the pushed skill's subpath AND a sibling file in the clone.
    (clone / sub / "SKILL.md").write_text("edited mkdocs\n")
    sibling = next(
        p for p in clone.iterdir()
        if p.is_dir() and p.name not in (".git", sub)
    )
    (sibling / "SKILL.md").write_text("edited sibling\n")

    r = CliRunner().invoke(cli, ["skill", "push", "--direct", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output

    show = subprocess.run(
        ["git", "-C", str(clone), "show", "--name-only", "--format=", "HEAD"],
        capture_output=True, text=True, env=scrub_git_env(), check=True,
    )
    changed = [ln for ln in show.stdout.splitlines() if ln.strip()]
    assert changed, "expected a commit touching the mkdocs subpath"
    assert all(p.startswith(f"{sub}/") for p in changed), changed


def test_owned_push_clean_subpath_reports_nothing(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned(parent_url, "mkdocs")
    r = CliRunner().invoke(cli, ["skill", "push", "--direct", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "nothing to push" in r.output.lower()


def test_owned_status_subpath_scoped_and_marked(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import parent_clone_path

    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    sub = entry["skillPath"]
    owner, repo = entry["source"].split("/", 1)
    clone = parent_clone_path(owner, repo, ref=entry.get("ref"), env=None)

    # Clean to start, and marked (owned).
    r = CliRunner().invoke(cli, ["skill", "status", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "clean" in r.output
    assert "(owned)" in r.output

    # Dirty a SIBLING subpath only → mkdocs must still read clean.
    sibling = next(
        p for p in clone.iterdir()
        if p.is_dir() and p.name not in (".git", sub)
    )
    (sibling / "SKILL.md").write_text("edited sibling\n")
    r2 = CliRunner().invoke(cli, ["skill", "status", "mkdocs", "-g"])
    assert "clean" in r2.output and "dirty" not in r2.output

    # Dirty mkdocs' own subpath → now dirty.
    (clone / sub / "SKILL.md").write_text("edited mkdocs\n")
    r3 = CliRunner().invoke(cli, ["skill", "status", "mkdocs", "-g"])
    assert "dirty" in r3.output


def test_owned_update_merges_not_resets_local_edits(tmp_path, monkeypatch):
    """skill update on an owned monorepo must NOT discard a local committed
    edit in the parent clone — it fetches + merges, never resets."""
    from agent_toolkit_cli.skill_paths import parent_clone_path

    parent_url, parent = _setup_parent(tmp_path, monkeypatch)
    _add_owned(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    sub = entry["skillPath"]
    owner, repo = entry["source"].split("/", 1)
    clone = parent_clone_path(owner, repo, ref=entry.get("ref"), env=None)

    # Commit a local edit in the clone (a self-improvement not yet pushed).
    marker = clone / sub / "LOCAL_EDIT.md"
    marker.write_text("local self-improvement\n")
    env = scrub_git_env()
    for cmd in (
        ["git", "-C", str(clone), "add", "--", sub],
        ["git", "-C", str(clone), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local edit"],
    ):
        subprocess.run(cmd, check=True, env=env)

    # Advance the upstream parent with an unrelated commit so update has
    # something to merge.
    (parent / "TOPLEVEL.md").write_text("upstream change\n")
    for cmd in (
        ["git", "-C", str(parent), "add", "."],
        ["git", "-C", str(parent), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream"],
    ):
        subprocess.run(cmd, check=True, env=env)

    r = CliRunner().invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    # The local edit survived the update (merge, not reset).
    assert marker.exists(), "skill update discarded a local owned edit"
