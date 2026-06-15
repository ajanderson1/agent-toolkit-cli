import subprocess
from pathlib import Path

import pytest

from agent_toolkit_cli.skill_git import (
    Divergence,
    GitError,
    GitWorkingTreeStatus,
    clone,
    divergence,
    fetch,
    fetch_ref,
    head_sha,
    merge,
    push,
    remote_head_sha,
    reset_hard,
    status,
)


def _is_shallow(repo: Path, env: dict) -> bool:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()
    return out == "true"


def _file_url(path: Path) -> str:
    """git ignores `--depth` for plain local-path clones ("--depth is ignored
    in local clones") — only `file://` (and real remotes) honour it. Tests that
    assert shallowness must therefore use a `file://` URL, mirroring the
    https://github.com/... URLs `skill import` resolves in production."""
    return f"file://{path}"


def _advance_upstream_once(git_sandbox, *, name="UPSTREAM.md", body="newer\n"):
    """Push one extra commit to the sandbox upstream so it has >1 commit —
    a prerequisite for `--depth=1` to produce a genuinely shallow clone."""
    helper = git_sandbox.upstream.parent / "depth-advance-helper"
    subprocess.run(["git", "clone", str(git_sandbox.upstream), str(helper)],
                   check=True, env=git_sandbox.env, capture_output=True)
    (helper / name).write_text(body)
    subprocess.run(["git", "-C", str(helper), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "commit", "-m", "advance"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "push", "origin", "main"],
                   check=True, env=git_sandbox.env, capture_output=True)


def test_clone_creates_working_tree(git_sandbox, tmp_path: Path):
    dest = tmp_path / "skill-out"
    clone(str(git_sandbox.upstream), dest, ref=None, env=git_sandbox.env)
    assert (dest / ".git").is_dir()
    assert (dest / "SKILL.md").exists()


def test_clone_failure_raises(tmp_path: Path):
    with pytest.raises(GitError):
        clone("file:///nonexistent.git", tmp_path / "x", ref=None, env={})


def test_clone_disables_prompt_and_batches_ssh(git_sandbox, tmp_path, monkeypatch):
    """Clone must fail loudly, never hang: GIT_TERMINAL_PROMPT=0 + BatchMode ssh (#251)."""
    from agent_toolkit_cli import skill_git

    captured: dict[str, dict] = {}
    real_run = subprocess.run

    def spy(cmd, **kwargs):
        if cmd[:2] == ["git", "clone"]:
            captured["env"] = dict(kwargs.get("env") or {})
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(skill_git.subprocess, "run", spy)
    clone(str(git_sandbox.upstream), tmp_path / "out", ref=None, env=git_sandbox.env)

    env = captured["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]


def test_clone_depth_makes_shallow_repo(git_sandbox, tmp_path: Path):
    """`depth=1` produces a shallow clone; the default stays full history (#259)."""
    # Needs >1 commit upstream, else depth-1 already covers all history and
    # git does not mark the clone shallow.
    _advance_upstream_once(git_sandbox)
    url = _file_url(git_sandbox.upstream)

    shallow = tmp_path / "shallow"
    clone(url, shallow, ref=None, env=git_sandbox.env, depth=1)
    assert (shallow / "SKILL.md").exists()
    assert _is_shallow(shallow, git_sandbox.env) is True

    full = tmp_path / "full"
    clone(url, full, ref=None, env=git_sandbox.env)
    assert _is_shallow(full, git_sandbox.env) is False


def test_clone_depth_preserves_prompt_and_ssh_hardening(
    git_sandbox, tmp_path, monkeypatch
):
    """A shallow clone must keep the #251 env hardening (no-hang guarantee)."""
    from agent_toolkit_cli import skill_git

    captured: dict[str, dict] = {}
    captured_cmd: dict[str, list] = {}
    real_run = subprocess.run

    def spy(cmd, **kwargs):
        if cmd[:2] == ["git", "clone"]:
            captured["env"] = dict(kwargs.get("env") or {})
            captured_cmd["cmd"] = list(cmd)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(skill_git.subprocess, "run", spy)
    clone(str(git_sandbox.upstream), tmp_path / "out", ref=None,
          env=git_sandbox.env, depth=1)

    env = captured["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]
    assert "--depth" in captured_cmd["cmd"]


def test_fetch_ref_makes_old_sha_checkoutable(git_sandbox, tmp_path):
    """On a depth-1 clone an older commit's tree is absent until fetch_ref
    pulls it — then checkout of that sha succeeds (#259)."""
    # The seed commit becomes the "old" sha once upstream advances past it.
    old_sha = head_sha(git_sandbox.clone, env=git_sandbox.env)
    _advance_upstream_once(git_sandbox)
    url = _file_url(git_sandbox.upstream)

    # Shallow clone of HEAD only — the old commit's tree is not present.
    shallow = tmp_path / "shallow"
    clone(url, shallow, ref=None, env=git_sandbox.env, depth=1)
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            ["git", "-C", str(shallow), "checkout", old_sha],
            check=True, env=git_sandbox.env, capture_output=True,
        )

    # fetch_ref pulls just that commit; the checkout now succeeds.
    fetch_ref(shallow, ref=old_sha, env=git_sandbox.env, depth=1)
    from agent_toolkit_cli.skill_git import checkout
    checkout(shallow, ref=old_sha, env=git_sandbox.env)
    assert head_sha(shallow, env=git_sandbox.env) == old_sha


def test_clone_respects_caller_ssh_command(git_sandbox, tmp_path, monkeypatch):
    """A caller-provided GIT_SSH_COMMAND is not clobbered by the BatchMode default."""
    from agent_toolkit_cli import skill_git

    captured: dict[str, dict] = {}
    real_run = subprocess.run

    def spy(cmd, **kwargs):
        if cmd[:2] == ["git", "clone"]:
            captured["env"] = dict(kwargs.get("env") or {})
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(skill_git.subprocess, "run", spy)
    env = {**git_sandbox.env, "GIT_SSH_COMMAND": "ssh -i /custom/key"}
    clone(str(git_sandbox.upstream), tmp_path / "out2", ref=None, env=env)

    assert captured["env"]["GIT_SSH_COMMAND"] == "ssh -i /custom/key"
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_status_clean(git_sandbox):
    s = status(git_sandbox.clone, env=git_sandbox.env)
    assert s == GitWorkingTreeStatus.CLEAN


def test_status_dirty(git_sandbox):
    (git_sandbox.clone / "SKILL.md").write_text("changed\n")
    s = status(git_sandbox.clone, env=git_sandbox.env)
    assert s == GitWorkingTreeStatus.DIRTY


def test_head_sha_returns_40_char_hex(git_sandbox):
    sha = head_sha(git_sandbox.clone, env=git_sandbox.env)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


def test_remote_head_sha_matches_head_initially(git_sandbox):
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert remote_head_sha(
        git_sandbox.clone, ref="main", env=git_sandbox.env
    ) == head_sha(git_sandbox.clone, env=git_sandbox.env)


def test_merge_fast_forwards_when_clean(git_sandbox):
    other = git_sandbox.upstream.parent / "other"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (other / "NEW.md").write_text("new file\n")
    subprocess.run(
        ["git", "-C", str(other), "add", "NEW.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(other), "commit", "-m", "advance"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(other), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    fetch(git_sandbox.clone, env=git_sandbox.env)
    merge(git_sandbox.clone, ref="main", env=git_sandbox.env)
    assert (git_sandbox.clone / "NEW.md").exists()


def test_push_pushes_local_commit(git_sandbox):
    (git_sandbox.clone / "LOCAL.md").write_text("self-improvement\n")
    subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "add", "LOCAL.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "commit", "-m", "local"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    push(git_sandbox.clone, ref="main", env=git_sandbox.env)
    other = git_sandbox.upstream.parent / "verify"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    assert (other / "LOCAL.md").exists()


def test_env_with_outer_git_dir_is_scrubbed(git_sandbox, monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/tmp/wrong")
    import os
    merged_env = os.environ.copy() | git_sandbox.env
    s = status(git_sandbox.clone, env=merged_env)
    assert s == GitWorkingTreeStatus.CLEAN


def test_is_git_repo_true_for_clone(git_sandbox):
    from agent_toolkit_cli.skill_git import is_git_repo
    assert is_git_repo(git_sandbox.clone) is True


def test_is_git_repo_false_for_plain_dir(tmp_path):
    from agent_toolkit_cli.skill_git import is_git_repo
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "SKILL.md").write_text("hi")
    assert is_git_repo(plain) is False


def test_is_git_repo_false_for_missing(tmp_path):
    from agent_toolkit_cli.skill_git import is_git_repo
    assert is_git_repo(tmp_path / "nope") is False


def test_commit_all_creates_commit_in_target_repo(git_sandbox):
    from agent_toolkit_cli.skill_git import commit_all

    (git_sandbox.clone / "LOCAL.md").write_text("self-improvement\n")
    commit_all(git_sandbox.clone, message="local change", env=git_sandbox.env)

    log = subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "log", "-1", "--format=%s"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    )
    assert log.stdout.strip() == "local change"


def test_commit_all_isolation_against_outer_git_dir(
    git_sandbox, tmp_path, monkeypatch,
):
    """Regression: even if a malicious/leaked GIT_DIR is in the caller's env,
    commit_all() must land its commit in the target repo, not the outer one.

    See feedback_git_env_leak.md — this exact failure produced a spurious
    'self-improvement: ...' commit on the worktree's own branch when
    _commit_dirty bypassed _scrub().
    """
    from agent_toolkit_cli.skill_git import commit_all

    # Create a separate "outer" repo to act as the would-be hijack target.
    outer = tmp_path / "outer"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(outer)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (outer / "seed").write_text("seed\n")
    subprocess.run(
        ["git", "-C", str(outer), "add", "seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(outer), "commit", "-m", "outer-seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    outer_head_before = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()

    # Simulate the leaked-env scenario.
    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer / ".git" / "index"))

    (git_sandbox.clone / "LOCAL.md").write_text("self-improvement\n")
    import os
    merged_env = os.environ.copy() | git_sandbox.env
    # Re-leak after the merge to make sure the helper itself scrubs:
    merged_env["GIT_DIR"] = str(outer / ".git")
    merged_env["GIT_INDEX_FILE"] = str(outer / ".git" / "index")

    commit_all(git_sandbox.clone, message="should-land-in-sandbox", env=merged_env)

    sandbox_head_msg = subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "log", "-1", "--format=%s"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert sandbox_head_msg == "should-land-in-sandbox"

    outer_head_after = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert outer_head_after == outer_head_before, (
        "GIT_DIR leak landed a commit in the outer repo"
    )


def test_reset_hard_snaps_working_tree_to_origin_ref(git_sandbox, tmp_path):
    """Advance upstream, then reset_hard() must pull the clone forward,
    discarding any local divergence."""
    # Advance upstream via a second clone.
    advancer = tmp_path / "advancer"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(advancer)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (advancer / "NEW.md").write_text("from upstream\n")
    subprocess.run(
        ["git", "-C", str(advancer), "add", "NEW.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(advancer), "commit", "-m", "advance"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(advancer), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    # Dirty up the clone with a local commit on a divergent path.
    (git_sandbox.clone / "LOCAL.md").write_text("local-divergence\n")
    subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "add", "LOCAL.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "commit", "-m", "local-only"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    fetch(git_sandbox.clone, env=git_sandbox.env)
    reset_hard(git_sandbox.clone, ref="main", env=git_sandbox.env)

    # Upstream's new file is present; local-only file is gone.
    assert (git_sandbox.clone / "NEW.md").exists()
    assert not (git_sandbox.clone / "LOCAL.md").exists()
    # HEAD now matches origin/main exactly.
    assert head_sha(git_sandbox.clone, env=git_sandbox.env) == remote_head_sha(
        git_sandbox.clone, ref="main", env=git_sandbox.env
    )


def test_reset_hard_isolation_against_outer_git_dir(
    git_sandbox, tmp_path, monkeypatch,
):
    """Regression-style guard: a leaked GIT_DIR / GIT_INDEX_FILE must not
    redirect the hard-reset into the outer repo.

    See feedback_git_env_leak.md — reset_hard() goes through _run() so the
    same scrub fires.
    """
    outer = tmp_path / "outer"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(outer)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (outer / "seed").write_text("seed\n")
    subprocess.run(
        ["git", "-C", str(outer), "add", "seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(outer), "commit", "-m", "outer-seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    outer_head_before = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()

    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer / ".git" / "index"))

    import os
    merged_env = os.environ.copy() | git_sandbox.env
    merged_env["GIT_DIR"] = str(outer / ".git")
    merged_env["GIT_INDEX_FILE"] = str(outer / ".git" / "index")

    fetch(git_sandbox.clone, env=merged_env)
    reset_hard(git_sandbox.clone, ref="main", env=merged_env)

    outer_head_after = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert outer_head_after == outer_head_before, (
        "GIT_DIR leak caused reset_hard to touch the outer repo"
    )


def test_commit_all_succeeds_without_global_git_identity(
    tmp_path: Path, monkeypatch,
):
    """Regression for #197: `commit_all()` must succeed on hosts with no
    global git identity (CI runners, fresh dev VMs, agent sandboxes).

    Reproduces the no-identity condition by pointing HOME at an empty
    directory and stripping every identity-bearing GIT_* env var. The
    production code path under test (`commit_all`) must inject a synthetic
    identity via `-c user.name/email` — same fix pattern PR #189 applied
    to `merge()`.

    Every subprocess in this test is given a scrubbed env (no GIT_*) — a
    leaked GIT_DIR / GIT_INDEX_FILE from a parent process would otherwise
    redirect seed commits into the outer repo (see memory
    feedback_git_env_leak.md).
    """
    from agent_toolkit_cli.skill_git import commit_all
    from tests.conftest import scrub_git_env

    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    for var in (
        "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
        "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
    ):
        monkeypatch.delenv(var, raising=False)

    seed_env = scrub_git_env()

    # Seed a minimal repo with one commit (using inline -c flags — the
    # production code path is what we're testing, not git init/seed).
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repo)],
        check=True, capture_output=True, env=seed_env,
    )
    (repo / "SEED.md").write_text("seed\n")
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-C", str(repo), "add", "SEED.md"],
        check=True, capture_output=True, env=seed_env,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-C", str(repo), "commit", "-q", "-m", "seed"],
        check=True, capture_output=True, env=seed_env,
    )

    # Now exercise commit_all() with no host identity available. This is
    # the exact failure condition from #197 — without the fix, git would
    # die with "fatal: empty ident name (...) not allowed". commit_all()
    # itself scrubs GIT_* via _run(), so env=None is the right call here.
    (repo / "LOCAL.md").write_text("local\n")
    commit_all(repo, message="should-land-without-host-identity", env=None)

    # Subject of HEAD matches what we passed.
    subj = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        check=True, capture_output=True, text=True, env=seed_env,
    ).stdout.strip()
    assert subj == "should-land-without-host-identity"

    # Lock in the synthetic-identity contract: HEAD's author must be the
    # agent-toolkit-cli identity. Asserting the actual fields makes this
    # test robust to /etc/gitconfig variations on other hosts — without
    # this, a host with /etc/gitconfig setting an identity could silently
    # green this test even if the production fix were reverted.
    head_author = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%an <%ae>"],
        check=True, capture_output=True, text=True, env=seed_env,
    ).stdout.strip()
    assert head_author == "agent-toolkit-cli <noreply@agent-toolkit-cli>", \
        f"commit_all must use synthetic identity, got: {head_author}"


def _advance_upstream(git_sandbox):
    """Push one new commit to upstream via a throwaway clone."""
    other = git_sandbox.upstream.parent / "advance-helper"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (other / "UPSTREAM.md").write_text("upstream advance\n")
    subprocess.run(["git", "-C", str(other), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(other), "commit", "-m", "upstream"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(other), "push", "origin", "main"],
                   check=True, env=git_sandbox.env, capture_output=True)


def _commit_local(git_sandbox, name="LOCAL.md", body="local change\n"):
    """Create one local commit in the clone (not pushed)."""
    (git_sandbox.clone / name).write_text(body)
    subprocess.run(["git", "-C", str(git_sandbox.clone), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(git_sandbox.clone), "commit", "-m", "local"],
                   check=True, env=git_sandbox.env, capture_output=True)


def test_divergence_up_to_date(git_sandbox):
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.UP_TO_DATE


def test_divergence_ahead(git_sandbox):
    _commit_local(git_sandbox)
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.AHEAD


def test_divergence_behind(git_sandbox):
    _advance_upstream(git_sandbox)
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.BEHIND


def test_divergence_diverged(git_sandbox):
    _commit_local(git_sandbox)
    _advance_upstream(git_sandbox)
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.DIVERGED


def test_divergence_does_not_fetch(git_sandbox):
    """divergence() reads only local refs — a behind clone reads UP_TO_DATE
    until the caller fetches. Pins the 'caller must fetch' contract."""
    _advance_upstream(git_sandbox)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.UP_TO_DATE
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert divergence(git_sandbox.clone, ref="main", env=git_sandbox.env) \
        == Divergence.BEHIND


def test_divergence_parses_left_right_count(monkeypatch):
    import agent_toolkit_cli.skill_git as g

    class _Fake:
        def __init__(self, out): self.stdout = out; self.stderr = ""

    cases = {"0\t0": g.Divergence.UP_TO_DATE, "2\t0": g.Divergence.AHEAD,
             "0\t3": g.Divergence.BEHIND, "2\t3": g.Divergence.DIVERGED}
    for out, expected in cases.items():
        monkeypatch.setattr(g, "_run", lambda *a, _o=out, **k: _Fake(_o))
        assert g.divergence(Path("/x"), ref="main", env=None) == expected


def test_normalise_git_url_collapses_forms():
    from agent_toolkit_cli.skill_git import normalise_git_url
    a = normalise_git_url("https://github.com/foo/bar.git")
    b = normalise_git_url("git@github.com:foo/bar.git")
    c = normalise_git_url("https://github.com/foo/bar")
    assert a == b == c == "github.com/foo/bar"


# --- legacy_bare_clone_for predicate (#412, shared by resolver + doctor) ---

def _bare_repo_on(path: Path, remote: str, branch: str) -> None:
    from tests.conftest import scrub_git_env
    path.mkdir(parents=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote],
        check=True, env=env,
    )
    subprocess.run(
        ["git", "-C", str(path), "checkout", "-q", "-b", branch],
        check=True, env=env,
    )
    (path / "f").write_text("x")
    subprocess.run(["git", "-C", str(path), "add", "f"], check=True, env=env)
    # Pin identity via -c so the commit works on a runner with no global git
    # config (scrub_git_env strips inherited GIT_AUTHOR_*/GIT_COMMITTER_*).
    subprocess.run(
        ["git", "-C", str(path),
         "-c", "user.name=t", "-c", "user.email=t@t.invalid",
         "commit", "-q", "-m", "c"],
        check=True, env=env,
    )


def test_legacy_bare_clone_for_none_ref_returns_none(tmp_path):
    from agent_toolkit_cli.skill_git import legacy_bare_clone_for
    bare = tmp_path / "_parents" / "o" / "r"
    suffixed = tmp_path / "_parents" / "o" / "r"
    assert legacy_bare_clone_for(
        suffixed, bare, ref=None, parent_url="https://github.com/o/r", env=None,
    ) is None


def test_legacy_bare_clone_for_non_git_bare_returns_none(tmp_path):
    from agent_toolkit_cli.skill_git import legacy_bare_clone_for
    bare = tmp_path / "_parents" / "o" / "r"
    bare.mkdir(parents=True)  # exists but is NOT a git repo
    suffixed = tmp_path / "_parents" / "o" / "r@main"
    assert legacy_bare_clone_for(
        suffixed, bare, ref="main", parent_url="https://github.com/o/r", env=None,
    ) is None


def test_legacy_bare_clone_for_matching_branch_adopts(tmp_path):
    from agent_toolkit_cli.skill_git import legacy_bare_clone_for
    url = "https://github.com/o/r"
    bare = tmp_path / "_parents" / "o" / "r"
    _bare_repo_on(bare, url, "main")
    suffixed = tmp_path / "_parents" / "o" / "r@main"
    assert legacy_bare_clone_for(
        suffixed, bare, ref="main", parent_url=url, env=None,
    ) == bare


def test_legacy_bare_clone_for_off_branch_returns_none(tmp_path):
    from agent_toolkit_cli.skill_git import legacy_bare_clone_for
    url = "https://github.com/o/r"
    bare = tmp_path / "_parents" / "o" / "r"
    _bare_repo_on(bare, url, "main")  # on main…
    suffixed = tmp_path / "_parents" / "o" / "r@dev"  # …but ref is dev
    assert legacy_bare_clone_for(
        suffixed, bare, ref="dev", parent_url=url, env=None,
    ) is None


def test_legacy_bare_clone_for_none_parent_url_returns_none(tmp_path):
    """A None parent_url fails safe rather than crashing in normalise_git_url
    — guards a future caller that forgets the entry.parent_url gate."""
    from agent_toolkit_cli.skill_git import legacy_bare_clone_for
    bare = tmp_path / "_parents" / "o" / "r"
    _bare_repo_on(bare, "https://github.com/o/r", "main")
    suffixed = tmp_path / "_parents" / "o" / "r@main"
    assert legacy_bare_clone_for(
        suffixed, bare, ref="main", parent_url=None, env=None,
    ) is None


def _bare_repo_detached_at_head(path: Path, remote: str) -> str:
    """Like _bare_repo_on but leaves the clone in DETACHED HEAD at its tip,
    returning that commit SHA. The existing helper only checks out named
    branches; the true-SHA-pin guard (#422) needs a detached clone."""
    from tests.conftest import scrub_git_env
    _bare_repo_on(path, remote, "main")
    env = scrub_git_env()
    sha = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, env=env,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(path), "checkout", "-q", sha],  # detach
        check=True, env=env,
    )
    return sha


def test_legacy_bare_clone_for_hex_named_branch_adopts(tmp_path):
    """#422 fix 1 — a bare clone checked out on a branch literally NAMED with a
    hex string (e.g. `dead123`) must be ADOPTED when ref equals that name.
    `looks_like_sha('dead123')` is True, so on the pre-fix code the SHA arm
    (`head_sha.startswith('dead123')`) fails and the clone is wrongly refused.
    The dual-check's branch arm (`current_branch == ref`) fixes this.

    Note (accepted residual, variant (b)): this same match means a SHA pin whose
    abbreviation equals a sibling skill's hex-named branch could wrong-adopt —
    astronomically unlikely, documented in `_checked_out_at_ref`."""
    from agent_toolkit_cli.skill_git import legacy_bare_clone_for
    url = "https://github.com/o/r"
    bare = tmp_path / "_parents" / "o" / "r"
    _bare_repo_on(bare, url, "dead123")  # branch literally named "dead123"
    suffixed = tmp_path / "_parents" / "o" / "r@dead123"
    assert legacy_bare_clone_for(
        suffixed, bare, ref="dead123", parent_url=url, env=None,
    ) == bare


def test_legacy_bare_clone_for_true_sha_pin_adopts(tmp_path):
    """#422 fix 1 regression guard — a clone DETACHED at the pinned commit, with
    ref = that SHA, is still adopted via the SHA arm (the dual-check must not
    break true SHA pins)."""
    from agent_toolkit_cli.skill_git import legacy_bare_clone_for
    url = "https://github.com/o/r"
    bare = tmp_path / "_parents" / "o" / "r"
    sha = _bare_repo_detached_at_head(bare, url)
    suffixed = tmp_path / "_parents" / "o" / f"r@{sha}"
    assert legacy_bare_clone_for(
        suffixed, bare, ref=sha, parent_url=url, env=None,
    ) == bare


def test_remote_matches_none_parent_url_is_false(tmp_path):
    from agent_toolkit_cli.skill_git import remote_matches
    bare = tmp_path / "r"
    _bare_repo_on(bare, "https://github.com/o/r", "main")
    assert remote_matches(bare, None, None) is False
