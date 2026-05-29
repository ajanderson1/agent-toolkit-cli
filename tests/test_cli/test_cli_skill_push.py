import json
import os
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_paths import canonical_skill_dir


def _add_and_install_project(runner, upstream_path, project):
    """Add to library then install at project scope with claude-code."""
    r = runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo",
    ])
    if r.exit_code != 0:
        return r
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])


def _setup_dirty_install(git_sandbox, tmp_path: Path, monkeypatch):
    """Add+install demo skill into a project and dirty SKILL.md.

    Returns (project, library_root, canonical) for the caller.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    # Set sandbox env but skip PATH — callers may have already adjusted PATH
    # to install a gh stub or hide gh, and the sandbox's snapshotted PATH
    # would clobber that.
    for k, v in git_sandbox.env.items():
        if k == "PATH":
            continue
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_and_install_project(runner, git_sandbox.upstream, project)
    assert r.exit_code == 0, r.output

    canonical = canonical_skill_dir("demo", scope="project", project=project)
    (canonical / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Improved.\n---\n# improved\n"
    )
    return project, library_root, canonical


def _install_gh_stub(tmp_path, monkeypatch, *, success=True, pr_url="https://github.com/x/y/pull/1"):
    """Lay a fake `gh` on PATH. With success=True, `gh auth status` exits 0
    and `gh pr create` prints `pr_url`. Otherwise both exit 1."""
    bin_dir = tmp_path / "gh-bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    if success:
        gh.write_text(
            "#!/bin/sh\n"
            'case "$1" in\n'
            "  auth) exit 0;;\n"
            f'  pr)   echo "{pr_url}"; exit 0;;\n'
            "esac\n"
            "exit 0\n"
        )
    else:
        gh.write_text("#!/bin/sh\nexit 1\n")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return bin_dir


def _hide_gh_from_path(tmp_path, monkeypatch):
    """Build a PATH that retains git (and its sub-helpers like
    `git-upload-pack`, `git-receive-pack`) but excludes any directory
    containing `gh`, so `shutil.which('gh')` returns None.

    Symlinks every `git*` binary from git's exec-path directory into a
    clean dir, then sets PATH to that dir only. Robust whether the host
    has `gh` installed or not.
    """
    bin_dir = tmp_path / "no-gh-bin"
    bin_dir.mkdir(exist_ok=True)
    import shutil
    git_path = shutil.which("git")
    if git_path is None:
        raise RuntimeError("git not on PATH; cannot run this test")
    git_dir = Path(git_path).parent
    for entry in git_dir.iterdir():
        if entry.name.startswith("git") and entry.name != "gh":
            target = bin_dir / entry.name
            if not target.exists():
                os.symlink(entry, target)
    monkeypatch.setenv("PATH", str(bin_dir))


def _upstream_heads(upstream: Path, env: dict[str, str]) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-remote", "--heads", str(upstream)],
        check=True, env=env, capture_output=True, text=True,
    )
    out = proc.stdout.strip().splitlines()
    return [line.split()[1].removeprefix("refs/heads/") for line in out]


def _upstream_main_sha(upstream: Path, env: dict[str, str]) -> str:
    proc = subprocess.run(
        ["git", "ls-remote", str(upstream), "main"],
        check=True, env=env, capture_output=True, text=True,
    )
    return proc.stdout.strip().split()[0]


def _read_project_lock(project: Path) -> dict:
    lock = project / "skills-lock.json"
    return json.loads(lock.read_text()) if lock.exists() else {}


# ---------------------------------------------------------------------------
# Default path (PR branch)
# ---------------------------------------------------------------------------


def test_push_default_opens_pr_branch(git_sandbox, tmp_path, monkeypatch):
    """Default path: creates a `skill/self-improvement-*` branch on upstream,
    leaves the tracked `main` ref unchanged, and prints the PR URL from gh."""
    _install_gh_stub(tmp_path, monkeypatch, pr_url="https://github.com/x/y/pull/42")
    project, _, _ = _setup_dirty_install(git_sandbox, tmp_path, monkeypatch)
    main_before = _upstream_main_sha(git_sandbox.upstream, git_sandbox.env)

    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output

    main_after = _upstream_main_sha(git_sandbox.upstream, git_sandbox.env)
    assert main_before == main_after, "main moved — should have been a PR branch"

    heads = _upstream_heads(git_sandbox.upstream, git_sandbox.env)
    pr_heads = [h for h in heads if h.startswith("skill/self-improvement-")]
    assert len(pr_heads) == 1, f"expected one PR branch, got: {heads}"
    assert pr_heads[0].endswith("-demo")

    assert "pushed branch skill/self-improvement-" in result.output
    assert "https://github.com/x/y/pull/42" in result.output

    # Default path must NOT advance local_sha (tracked ref unchanged).
    lock_data = _read_project_lock(project)
    entry = lock_data["skills"]["demo"]
    assert "localSha" not in entry


def test_push_default_without_gh_prints_branch_hint(
    git_sandbox, tmp_path, monkeypatch,
):
    """Default path still pushes the PR branch when gh is missing; stdout
    contains a manual-PR hint instead of a PR URL."""
    _hide_gh_from_path(tmp_path, monkeypatch)
    project, _, _ = _setup_dirty_install(git_sandbox, tmp_path, monkeypatch)
    main_before = _upstream_main_sha(git_sandbox.upstream, git_sandbox.env)

    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output

    main_after = _upstream_main_sha(git_sandbox.upstream, git_sandbox.env)
    assert main_before == main_after, "main moved without gh available"

    heads = _upstream_heads(git_sandbox.upstream, git_sandbox.env)
    assert any(h.startswith("skill/self-improvement-") for h in heads), heads

    assert "pushed branch skill/self-improvement-" in result.output
    assert "--direct" in result.output


def test_push_default_returns_canonical_to_base_ref(
    git_sandbox, tmp_path, monkeypatch,
):
    """After a PR-branch push the canonical skill repo is checked back to
    the tracked ref, so the next `skill update` merges into the right
    branch instead of into the throwaway PR branch."""
    _install_gh_stub(tmp_path, monkeypatch)
    project, _, canonical = _setup_dirty_install(
        git_sandbox, tmp_path, monkeypatch,
    )

    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output

    head_branch = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head_branch == "main", (
        f"canonical repo left on {head_branch!r}; should be back on main"
    )


def test_push_default_batch_branch_names_are_unique(
    git_sandbox, tmp_path, monkeypatch,
):
    """Two slugs pushed in the same invocation must produce distinct PR
    branches even when the wall clock ticks within a second."""
    _install_gh_stub(tmp_path, monkeypatch)
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        if k == "PATH":
            continue
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    # Install two skills, both pointing at the same upstream (a second
    # bare repo so they can be pushed independently).
    second_upstream = tmp_path / "upstream2.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(second_upstream)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(tmp_path / "seed2")],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path / "seed2"), "remote", "set-url",
         "origin", str(second_upstream)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path / "seed2"), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    for slug, upstream in (("demo1", git_sandbox.upstream),
                           ("demo2", second_upstream)):
        r = runner.invoke(main, [
            "skill", "add", str(upstream), "--slug", slug,
        ])
        assert r.exit_code == 0, r.output
        r = runner.invoke(main, [
            "--project", str(project),
            "skill", "install", slug, "--scope", "project",
            "--agents", "claude-code",
        ])
        assert r.exit_code == 0, r.output
        canonical = canonical_skill_dir(slug, scope="project", project=project)
        (canonical / "SKILL.md").write_text(
            f"---\nname: {slug}\ndescription: Improved {slug}.\n---\n# {slug}\n"
        )

    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "demo1", "demo2", "-p",
    ])
    assert result.exit_code == 0, result.output

    heads1 = _upstream_heads(git_sandbox.upstream, git_sandbox.env)
    heads2 = _upstream_heads(second_upstream, git_sandbox.env)
    pr1 = [h for h in heads1 if h.startswith("skill/self-improvement-")]
    pr2 = [h for h in heads2 if h.startswith("skill/self-improvement-")]
    assert len(pr1) == 1, heads1
    assert len(pr2) == 1, heads2
    # Each branch name encodes its slug, so even at the same wall-clock
    # second the two are distinguishable.
    assert pr1[0] != pr2[0]
    assert pr1[0].endswith("-demo1")
    assert pr2[0].endswith("-demo2")


def test_push_default_gh_auth_failure_falls_back(
    git_sandbox, tmp_path, monkeypatch,
):
    """gh present but `gh auth status` fails → fall back to hint."""
    _install_gh_stub(tmp_path, monkeypatch, success=False)
    project, _, _ = _setup_dirty_install(git_sandbox, tmp_path, monkeypatch)

    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert "pushed branch skill/self-improvement-" in result.output
    assert "PR:" not in result.output
    assert "--direct" in result.output


# ---------------------------------------------------------------------------
# Opt-in: --direct path
# ---------------------------------------------------------------------------


def test_push_direct_pushes_to_tracked_ref(git_sandbox, tmp_path, monkeypatch):
    """`--direct` preserves the pre-#221 behaviour: commit + push to main."""
    project, _, _ = _setup_dirty_install(git_sandbox, tmp_path, monkeypatch)

    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "--direct", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert "pushed" in result.output

    verify = tmp_path / "verify"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(verify)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    assert "Improved" in (verify / "SKILL.md").read_text()


def test_push_direct_updates_lockfile_local_sha(
    git_sandbox, tmp_path, monkeypatch,
):
    project, _, _ = _setup_dirty_install(git_sandbox, tmp_path, monkeypatch)

    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "--direct", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output

    lock_data = _read_project_lock(project)
    entry = lock_data["skills"]["demo"]
    assert "localSha" in entry
    assert entry["localSha"] == _upstream_main_sha(
        git_sandbox.upstream, git_sandbox.env,
    )


# ---------------------------------------------------------------------------
# Shared invariants
# ---------------------------------------------------------------------------


def test_push_clean_is_noop(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_and_install_project(runner, git_sandbox.upstream, project)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "demo", "-p",
    ])
    assert result.exit_code == 0
    assert "clean" in result.output.lower() or "nothing" in result.output.lower()


def test_push_no_flag_outside_project_uses_global(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """No flag + no project lock at cwd → push consults global lock (#220).

    Mirrors the #216 list/status fix for verbs that mutate.
    """
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output

    not_a_project = tmp_path / "not-a-project"
    not_a_project.mkdir()
    result = runner.invoke(main, [
        "--project", str(not_a_project), "skill", "push", "demo",
    ])
    assert result.exit_code == 0, result.output
    assert "not in lock" not in result.output
    assert "demo" in result.output  # at least a slug-bearing status line


def test_push_clean_is_noop_under_direct(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_and_install_project(runner, git_sandbox.upstream, project)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "--direct", "demo", "-p",
    ])
    assert result.exit_code == 0
    assert "clean" in result.output.lower() or "nothing" in result.output.lower()


def test_push_does_not_leak_into_outer_repo(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """Regression: a leaked GIT_DIR from the parent process must not divert
    the self-improvement commit into the outer repo.

    See feedback_git_env_leak.md.
    """
    _install_gh_stub(tmp_path, monkeypatch)
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    # Set up an "outer" repo to act as the would-be hijack target.
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

    # Simulate the leak.
    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer / ".git" / "index"))

    runner = CliRunner()
    r = _add_and_install_project(runner, git_sandbox.upstream, project)
    assert r.exit_code == 0, r.output

    canonical = canonical_skill_dir("demo", scope="project", project=project)
    (canonical / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Improved.\n---\n# improved\n"
    )

    result = runner.invoke(main, [
        "--project", str(project), "skill", "push", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output

    outer_head_after = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert outer_head_after == outer_head_before, (
        "push leaked into outer repo (GIT_DIR/GIT_INDEX_FILE scrub failed)"
    )


# ---------------------------------------------------------------------------
# Global-scope push helpers
# ---------------------------------------------------------------------------


def _setup_global_demo(git_sandbox, tmp_path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        if k == "PATH":
            continue  # callers may have adjusted PATH (e.g. gh stub); don't clobber
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                             "--slug", "demo"])
    assert r.exit_code == 0, r.output
    return runner, library_root


# Reads git refs directly (not via skill_git) so the assertion is an independent
# oracle — a bug in skill_git's SHA helpers can't mask a push-stranding bug.
def _rev_parse(canonical, ref, env):
    return subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", ref],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()


def test_push_clean_with_commits_ahead_pushes_them(git_sandbox, tmp_path, monkeypatch):
    """#280 (Gap Ledger §4) fix: a clean tree with local commits ahead of
    origin is NOT 'nothing to push' — `--direct` publishes the committed work
    and HEAD reaches the remote. (This test previously pinned the bug.)"""
    runner, root = _setup_global_demo(git_sandbox, tmp_path, monkeypatch)
    canonical = root / "demo"
    # Commit locally (clean working tree, but ahead of origin).
    (canonical / "NEW.md").write_text("ahead commit\n")
    subprocess.run(["git", "-C", str(canonical), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(canonical), "commit", "-m", "ahead"],
                   check=True, env=git_sandbox.env, capture_output=True)

    result = runner.invoke(main, ["skill", "push", "demo", "-g", "--direct"])
    assert result.exit_code == 0, result.output
    assert "nothing to push" not in result.output
    assert "pushed" in result.output

    # The committed-but-unpushed work reached the remote.
    assert _rev_parse(canonical, "HEAD", git_sandbox.env) \
        == _rev_parse(canonical, "origin/main", git_sandbox.env)


def test_push_clean_ahead_default_opens_pr_branch(git_sandbox, tmp_path, monkeypatch):
    """#280: clean tree + committed-ahead work in default (PR) mode pushes a
    `skill/self-improvement-*` branch carrying the commit, leaves `main`
    untouched, and prints the PR URL."""
    _install_gh_stub(tmp_path, monkeypatch, pr_url="https://github.com/x/y/pull/77")
    runner, root = _setup_global_demo(git_sandbox, tmp_path, monkeypatch)
    canonical = root / "demo"
    main_before = _upstream_main_sha(git_sandbox.upstream, git_sandbox.env)

    (canonical / "NEW.md").write_text("ahead commit\n")
    subprocess.run(["git", "-C", str(canonical), "add", "-A"],
                   check=True, env=git_sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(canonical), "commit", "-m", "ahead"],
                   check=True, env=git_sandbox.env, capture_output=True)

    result = runner.invoke(main, ["skill", "push", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert "nothing to push" not in result.output
    assert "pushed branch skill/self-improvement-" in result.output
    assert "https://github.com/x/y/pull/77" in result.output

    # main untouched — the commit lives on the PR branch.
    assert _upstream_main_sha(git_sandbox.upstream, git_sandbox.env) == main_before
    heads = _upstream_heads(git_sandbox.upstream, git_sandbox.env)
    pr_heads = [h for h in heads if h.startswith("skill/self-improvement-")]
    assert len(pr_heads) == 1, heads
    # Canonical repo restored to base so a later `skill update` merges correctly.
    head_branch = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head_branch == "main", head_branch


def test_push_clean_up_to_date_still_noop(git_sandbox, tmp_path, monkeypatch):
    """#280 guard: a genuinely up-to-date clean clone still prints
    'clean — nothing to push' (UP_TO_DATE is the only true nothing-to-push)."""
    runner, root = _setup_global_demo(git_sandbox, tmp_path, monkeypatch)
    result = runner.invoke(main, ["skill", "push", "demo", "-g", "--direct"])
    assert result.exit_code == 0, result.output
    assert "nothing to push" in result.output


def test_push_dirty_direct_pushes(git_sandbox, tmp_path, monkeypatch):
    """Dirty working tree + --direct commits and pushes; HEAD reaches the remote.

    Also documents current behaviour for Gap Ledger §5: push performs NO
    upstream-ownership verification — a dirty skill pushes whenever
    `git push` succeeds, even though the upstream is not checked for
    ownership.  See Gap Ledger §5."""
    runner, root = _setup_global_demo(git_sandbox, tmp_path, monkeypatch)
    canonical = root / "demo"
    (canonical / "SKILL.md").write_text("self-improvement\n")  # dirty
    result = runner.invoke(main, ["skill", "push", "demo", "-g", "--direct"])
    assert result.exit_code == 0, result.output
    assert "pushed" in result.output
    # No ownership gate: the commit reached the remote.
    assert _rev_parse(canonical, "HEAD", git_sandbox.env) \
        == _rev_parse(canonical, "origin/main", git_sandbox.env)


def test_push_monorepo_refused(monorepo_skill):
    """read-only monorepo skill → push refused, exit 1."""
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "push", "mkdocs", "-g"])
    assert result.exit_code == 1
    assert "read-only" in result.output
