"""commit_paths / status_path operate scoped to a subpath of a repo."""
import subprocess
from pathlib import Path

from agent_toolkit_cli import skill_git

from tests.conftest import scrub_git_env


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "a").mkdir(parents=True)
    (repo / "b").mkdir(parents=True)
    (repo / "a" / "f.txt").write_text("a1\n")
    (repo / "b" / "f.txt").write_text("b1\n")
    env = scrub_git_env()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, env=env)
    return repo


def test_status_path_clean_then_dirty(tmp_path):
    repo = _init_repo(tmp_path)
    assert skill_git.status_path(repo, "a", env=None) == skill_git.GitWorkingTreeStatus.CLEAN
    (repo / "a" / "f.txt").write_text("a2\n")
    assert skill_git.status_path(repo, "a", env=None) == skill_git.GitWorkingTreeStatus.DIRTY
    # b is untouched, so scoped to b it is still clean.
    assert skill_git.status_path(repo, "b", env=None) == skill_git.GitWorkingTreeStatus.CLEAN


def test_commit_paths_only_commits_the_scoped_subpath(tmp_path):
    repo = _init_repo(tmp_path)
    # Make BOTH subpaths dirty, but commit only "a".
    (repo / "a" / "f.txt").write_text("a2\n")
    (repo / "b" / "f.txt").write_text("b2\n")
    skill_git.commit_paths(repo, message="edit a only", paths=["a"], env=None)
    # a is now clean (committed); b is still dirty (not committed).
    assert skill_git.status_path(repo, "a", env=None) == skill_git.GitWorkingTreeStatus.CLEAN
    assert skill_git.status_path(repo, "b", env=None) == skill_git.GitWorkingTreeStatus.DIRTY
    # The last commit touched only a/f.txt.
    show = subprocess.run(
        ["git", "-C", str(repo), "show", "--name-only", "--format=", "HEAD"],
        capture_output=True, text=True, env=scrub_git_env(), check=True,
    )
    changed = [ln for ln in show.stdout.splitlines() if ln.strip()]
    assert changed == ["a/f.txt"]


def test_commit_paths_noop_when_subpath_clean(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "b" / "f.txt").write_text("b2\n")  # dirty elsewhere
    # Committing "a" (clean) should report nothing staged and not create a commit.
    committed = skill_git.commit_paths(repo, message="noop", paths=["a"], env=None)
    assert committed is False
