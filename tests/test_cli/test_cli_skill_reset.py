"""CLI tests for `agent-toolkit-cli skill reset`.

Covers the acceptance criteria from issue #170:
  - clean reset succeeds
  - dirty refused without --force
  - dirty --force succeeds
  - lock updated
  - missing-from-lock surfaces an error
  - multi-slug form
"""
import json
import shutil
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


# --- helpers (local copies, mirrors test_cli_skill_update.py / _push.py) ---


def _add_and_install_project(runner, upstream_path, project, slug="demo"):
    """Add to library then install at project scope with claude-code."""
    r = runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", slug,
    ])
    if r.exit_code != 0:
        return r
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "install", slug, "--scope", "project",
        "--agents", "claude-code",
    ])


def _advance_upstream(git_sandbox, files: dict[str, str], *,
                      upstream: Path | None = None):
    """Push `files` to `upstream` (defaults to git_sandbox.upstream) via a
    fresh advancer clone."""
    upstream_path = upstream if upstream is not None else git_sandbox.upstream
    other = upstream_path.parent / f"advancer-{upstream_path.name}"
    if other.exists():
        shutil.rmtree(other)
    subprocess.run(
        ["git", "clone", str(upstream_path), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    for name, content in files.items():
        (other / name).write_text(content)
        subprocess.run(
            ["git", "-C", str(other), "add", name],
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


def _set_sandbox_env(monkeypatch, git_sandbox, library_root: Path):
    """Wire pytest monkeypatch with git_sandbox env + library root."""
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))


# --- tests ---


def test_reset_clean_snaps_to_upstream(git_sandbox, tmp_path: Path, monkeypatch):
    """Clean tree, upstream has advanced → reset pulls the advance in."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    _set_sandbox_env(monkeypatch, git_sandbox, library_root)

    runner = CliRunner()
    assert _add_and_install_project(runner, git_sandbox.upstream, project).exit_code == 0

    _advance_upstream(git_sandbox, {"NEW.md": "from upstream\n"})

    result = runner.invoke(main, [
        "--project", str(project), "skill", "reset", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output
    canonical = project / ".agents" / "skills" / "demo"
    assert (canonical / "NEW.md").exists()
    assert "reset to" in result.output


def test_reset_no_flag_outside_project_uses_global(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """No flag + no project lock at cwd → reset consults global lock (#220).

    Mirrors the #216 list/status fix for verbs that mutate.
    """
    library_root = tmp_path / "lib" / "skills"
    _set_sandbox_env(monkeypatch, git_sandbox, library_root)

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output

    not_a_project = tmp_path / "not-a-project"
    not_a_project.mkdir()
    result = runner.invoke(main, [
        "--project", str(not_a_project), "skill", "reset", "demo",
    ])
    assert result.exit_code == 0, result.output
    assert "not in lock" not in result.output
    assert "reset to" in result.output


def test_reset_refuses_dirty_without_force(git_sandbox, tmp_path: Path, monkeypatch):
    """Dirty working tree → reset refuses, exits non-zero, edits untouched."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    _set_sandbox_env(monkeypatch, git_sandbox, library_root)

    runner = CliRunner()
    assert _add_and_install_project(runner, git_sandbox.upstream, project).exit_code == 0

    canonical = project / ".agents" / "skills" / "demo"
    dirty_text = "---\nname: demo\ndescription: Dirty local edit.\n---\n# dirty\n"
    (canonical / "SKILL.md").write_text(dirty_text)

    # Also advance upstream so we can distinguish "refused" from "no-op".
    _advance_upstream(git_sandbox, {"NEW.md": "from upstream\n"})

    result = runner.invoke(main, [
        "--project", str(project), "skill", "reset", "demo", "-p",
    ])
    assert result.exit_code != 0
    assert "dirty" in result.output.lower()
    # The dirty edit is still there (reset did NOT fire).
    assert (canonical / "SKILL.md").read_text() == dirty_text
    # The upstream advance was NOT pulled in.
    assert not (canonical / "NEW.md").exists()


def test_reset_force_discards_dirty_tree(git_sandbox, tmp_path: Path, monkeypatch):
    """Dirty working tree + --force → reset wipes local edits and snaps."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    _set_sandbox_env(monkeypatch, git_sandbox, library_root)

    runner = CliRunner()
    assert _add_and_install_project(runner, git_sandbox.upstream, project).exit_code == 0

    canonical = project / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Dirty.\n---\n# dirty\n"
    )

    _advance_upstream(git_sandbox, {"NEW.md": "from upstream\n"})

    result = runner.invoke(main, [
        "--project", str(project), "skill", "reset", "demo", "-p", "--force",
    ])
    assert result.exit_code == 0, result.output
    # Upstream pulled in.
    assert (canonical / "NEW.md").exists()
    # Local edit discarded — SKILL.md is back to the seed content.
    assert "dirty" not in (canonical / "SKILL.md").read_text().lower()


def test_reset_updates_lock_shas(git_sandbox, tmp_path: Path, monkeypatch):
    """After reset, local_sha == upstream_sha == origin/main HEAD."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    _set_sandbox_env(monkeypatch, git_sandbox, library_root)

    runner = CliRunner()
    assert _add_and_install_project(runner, git_sandbox.upstream, project).exit_code == 0

    _advance_upstream(git_sandbox, {"NEW.md": "from upstream\n"})

    result = runner.invoke(main, [
        "--project", str(project), "skill", "reset", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output

    # Read project lock — v1 uses localSha / upstreamSha (camelCase).
    lock_data = json.loads((project / "skills-lock.json").read_text())
    entry = lock_data["skills"]["demo"]
    assert entry["localSha"] == entry["upstreamSha"]
    assert len(entry["localSha"]) == 40

    # And both equal the upstream's actual HEAD.
    upstream_head = subprocess.run(
        ["git", "-C", str(git_sandbox.upstream), "rev-parse", "refs/heads/main"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert entry["localSha"] == upstream_head


def test_reset_missing_slug_errors(git_sandbox, tmp_path: Path, monkeypatch):
    """Unknown slug → exits non-zero with a 'not in lock' message."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    _set_sandbox_env(monkeypatch, git_sandbox, library_root)

    runner = CliRunner()
    # Install something so the lock file exists.
    assert _add_and_install_project(runner, git_sandbox.upstream, project).exit_code == 0

    result = runner.invoke(main, [
        "--project", str(project), "skill", "reset", "bogus-slug", "-p",
    ])
    assert result.exit_code != 0
    assert "bogus-slug" in result.output
    assert "not in lock" in result.output


def test_reset_multi_slug(git_sandbox, tmp_path: Path, monkeypatch):
    """Two slugs → both get reset, both lock entries refreshed."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    _set_sandbox_env(monkeypatch, git_sandbox, library_root)

    runner = CliRunner()
    # Install the first slug (uses git_sandbox.upstream).
    assert _add_and_install_project(
        runner, git_sandbox.upstream, project, slug="demo",
    ).exit_code == 0

    # Stand up a second upstream so we can install a second slug.
    upstream2 = tmp_path / "upstream2.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(upstream2)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    seed2 = tmp_path / "seed2"
    seed2.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(seed2)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (seed2 / "SKILL.md").write_text(
        "---\nname: demo2\ndescription: Second test skill.\n---\n# demo2\n"
    )
    subprocess.run(
        ["git", "-C", str(seed2), "add", "SKILL.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed2), "commit", "-m", "seed2"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed2), "remote", "add", "origin", str(upstream2)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed2), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    assert _add_and_install_project(
        runner, upstream2, project, slug="demo2",
    ).exit_code == 0

    # Advance both upstreams.
    _advance_upstream(git_sandbox, {"NEW1.md": "one\n"})
    _advance_upstream(git_sandbox, {"NEW2.md": "two\n"}, upstream=upstream2)

    result = runner.invoke(main, [
        "--project", str(project), "skill", "reset", "demo", "demo2", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert (project / ".agents" / "skills" / "demo" / "NEW1.md").exists()
    assert (project / ".agents" / "skills" / "demo2" / "NEW2.md").exists()

    lock_data = json.loads((project / "skills-lock.json").read_text())
    for slug in ("demo", "demo2"):
        entry = lock_data["skills"][slug]
        assert entry["localSha"] == entry["upstreamSha"]
