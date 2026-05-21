"""skill update for monorepo entries pulls the parent clone."""
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli

from tests.conftest import scrub_git_env


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _init_parent(tmp_path: Path) -> Path:
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
    return parent


def test_update_monorepo_pulls_parent_and_reflects_new_content(
    tmp_path, monkeypatch,
):
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    # Mutate the parent.
    (parent / "mkdocs" / "SKILL.md").write_text(
        "---\nname: mkdocs\ndescription: updated\n---\nnew body\n"
    )
    env = scrub_git_env()
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "update"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code == 0, r2.output

    canonical = library / "skills" / "mkdocs"
    assert "new body" in (canonical / "SKILL.md").read_text()


def test_update_monorepo_copy_mode_re_copies(tmp_path, monkeypatch):
    """When materialised: 'copy' is set, update must re-copy from the refreshed
    parent (symlink would auto-pickup; copy must be explicit)."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    # Force the copy fallback for the install.
    from pathlib import Path as _Path
    def _refuse_symlink(self, target, target_is_directory=False):
        raise OSError("simulated: platform refuses symlinks")
    monkeypatch.setattr(_Path, "symlink_to", _refuse_symlink)

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    canonical = library / "skills" / "mkdocs"
    # Should be a real directory, not a symlink.
    assert canonical.is_dir() and not canonical.is_symlink()

    # Mutate the parent.
    (parent / "mkdocs" / "SKILL.md").write_text(
        "---\nname: mkdocs\ndescription: updated\n---\nupdated copy body\n"
    )
    env = scrub_git_env()
    import subprocess as _sp
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "update"],
    ):
        _sp.run(cmd, cwd=parent, check=True, env=env)

    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code == 0, r2.output

    # Re-copy should have happened: the stale snapshot is gone.
    assert "updated copy body" in (canonical / "SKILL.md").read_text()


def test_update_monorepo_merges_local_and_upstream_commits(
    tmp_path, monkeypatch,
):
    """User commits a local change to the parent clone, upstream gets a
    non-conflicting commit. `skill update` merges both."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    # `_init_parent` produces an `owner/repo` of `_/parent` because
    # we cloned from a file:// URL; locate the clone by walking _parents/.
    candidates = list((library / "skills" / "_parents").glob("*/*"))
    assert len(candidates) == 1, candidates
    parent_clone = candidates[0]

    env = scrub_git_env()

    # 1. Local commit in the parent clone (the "I edited it" path).
    (parent_clone / "mkdocs" / "LOCAL.md").write_text("local change\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local edit"],
    ):
        subprocess.run(cmd, cwd=parent_clone, check=True, env=env)

    # 2. Upstream commit on a different file.
    (parent / "mkdocs" / "UPSTREAM.md").write_text("upstream change\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream edit"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    # 3. Update — should merge.
    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code == 0, r2.output

    canonical = library / "skills" / "mkdocs"
    assert (canonical / "LOCAL.md").read_text() == "local change\n"
    assert (canonical / "UPSTREAM.md").read_text() == "upstream change\n"


def test_update_monorepo_surfaces_real_merge_conflict(tmp_path, monkeypatch):
    """Both local and upstream change the same file → `skill update` exits
    non-zero, names the parent clone path, leaves the clone mid-merge."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    candidates = list((library / "skills" / "_parents").glob("*/*"))
    parent_clone = candidates[0]

    env = scrub_git_env()
    target = "mkdocs/SKILL.md"

    # Local change.
    (parent_clone / target).write_text("LOCAL VERSION\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local"],
    ):
        subprocess.run(cmd, cwd=parent_clone, check=True, env=env)

    # Upstream change to the same file.
    (parent / target).write_text("UPSTREAM VERSION\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    # Update — should fail with a useful message.
    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code != 0, r2.output
    assert str(parent_clone) in r2.output, r2.output
    assert "mkdocs:" in r2.output, r2.output

    # The parent clone should be mid-merge (MERGE_HEAD present).
    assert (parent_clone / ".git" / "MERGE_HEAD").exists(), \
        "parent clone should be left mid-merge so user can resolve"

    # User resolves the conflict and commits — `skill update` should succeed.
    env_recover = scrub_git_env()
    (parent_clone / target).write_text("RESOLVED\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "--no-edit"],
    ):
        subprocess.run(cmd, cwd=parent_clone, check=True, env=env_recover)

    r3 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r3.exit_code == 0, r3.output
    canonical = library / "skills" / "mkdocs"
    assert canonical / "SKILL.md"  # exists
    assert (canonical / "SKILL.md").read_text() == "RESOLVED\n"


def test_update_monorepo_refuses_dirty_working_tree(tmp_path, monkeypatch):
    """Uncommitted change in the parent clone → `skill update` exits
    non-zero with a message telling the user to commit or stash."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    candidates = list((library / "skills" / "_parents").glob("*/*"))
    parent_clone = candidates[0]

    # Leave an uncommitted change to a file the upstream commit will also
    # change — git merge refuses when the dirty path would be overwritten.
    (parent_clone / "mkdocs" / "SKILL.md").write_text("dirty\n")

    # Upstream change to the same file so the merge cannot proceed.
    env = scrub_git_env()
    (parent / "mkdocs" / "SKILL.md").write_text("upstream version\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code != 0, r2.output
    assert str(parent_clone) in r2.output, r2.output

    # Git refused before starting the merge — no MERGE_HEAD, dirty file still present.
    assert not (parent_clone / ".git" / "MERGE_HEAD").exists(), \
        "dirty-tree refusal should reject before starting merge"
    assert (parent_clone / "mkdocs" / "SKILL.md").read_text() == "dirty\n", \
        "user's uncommitted change must survive"
