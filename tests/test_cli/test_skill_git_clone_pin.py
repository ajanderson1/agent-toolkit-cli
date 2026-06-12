"""#345: skill_git.clone_pinned_or_branch — SHA-aware clone helper."""
import subprocess

from agent_toolkit_cli import skill_git


def _git(env, cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()


def test_clone_pinned_lands_on_sha(tmp_path, git_sandbox):
    """A SHA pin must NOT go through `git clone --branch <sha>` (git rejects
    it) — clone at HEAD, then checkout the pin."""
    first_sha = _git(git_sandbox.env, git_sandbox.clone, "rev-parse", "HEAD")
    (git_sandbox.clone / "EXTRA.md").write_text("second\n")
    _git(git_sandbox.env, git_sandbox.clone, "add", "-A")
    _git(git_sandbox.env, git_sandbox.clone, "commit", "-m", "second")
    _git(git_sandbox.env, git_sandbox.clone, "push", "origin", "main")

    dest = tmp_path / "pinned"
    skill_git.clone_pinned_or_branch(
        str(git_sandbox.upstream), dest, ref=first_sha, env=git_sandbox.env,
    )
    assert _git(git_sandbox.env, dest, "rev-parse", "HEAD") == first_sha
    assert not (dest / "EXTRA.md").exists()


def test_clone_branch_lands_on_tip(tmp_path, git_sandbox):
    """A branch ref clones --branch and lands on the current tip."""
    dest = tmp_path / "tracking"
    skill_git.clone_pinned_or_branch(
        str(git_sandbox.upstream), dest, ref="main", env=git_sandbox.env,
    )
    tip = _git(git_sandbox.env, git_sandbox.clone, "rev-parse", "HEAD")
    assert _git(git_sandbox.env, dest, "rev-parse", "HEAD") == tip
    assert _git(git_sandbox.env, dest, "rev-parse", "--abbrev-ref", "HEAD") == "main"
