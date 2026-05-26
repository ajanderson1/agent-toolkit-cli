"""Tests for `skill import` — additive cross-machine library sync."""
import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_reconstruct_helper_clones_single_repo_and_pins(
    git_sandbox, tmp_path, monkeypatch
):
    """reconstruct_skill_into_library clones a single repo and honours pin_sha."""
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli.commands.skill import reconstruct_skill_into_library
    from agent_toolkit_cli.skill_paths import library_skill_path
    from agent_toolkit_cli.skill_source import parse_source

    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    parsed = parse_source(str(git_sandbox.upstream))
    target_sha = skill_git.head_sha(git_sandbox.clone, env=None)

    upstream_sha, local_sha = reconstruct_skill_into_library(
        parsed, "demo", pin_sha=target_sha,
    )

    assert (library_skill_path("demo") / "SKILL.md").exists()
    assert local_sha == target_sha


NOTE_UPSTREAM = "pinned to upstream commits"
NOTE_PROJECT = "Project-scoped skills"
NOTE_AGENTS = "not installed for any agent"


def test_import_missing_file_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(tmp_path / "nope.json")])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_import_empty_file_imports_nothing_but_prints_notes(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    incoming = tmp_path / "incoming.json"
    incoming.write_text('{"version": 1, "skills": {}}')
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "0 added" in result.output
    assert NOTE_UPSTREAM in result.output
    assert NOTE_PROJECT in result.output
    assert NOTE_AGENTS in result.output


def _write_incoming_for(upstream: Path, slug: str, sha: str, dest: Path) -> Path:
    """Write a v1 lock naming one single-repo skill pinned to `sha`."""
    dest.write_text(json.dumps({
        "version": 1,
        "skills": {
            slug: {
                "source": str(upstream),
                "sourceType": "git",
                "skillPath": "SKILL.md",
                "upstreamSha": sha,
                "localSha": sha,
            }
        },
    }))
    return dest


def test_import_adds_new_single_skill_pinned(git_sandbox, tmp_path, monkeypatch):
    from agent_toolkit_cli import skill_git
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    sha = skill_git.head_sha(git_sandbox.clone, env=None)
    incoming = _write_incoming_for(
        git_sandbox.upstream, "demo", sha, tmp_path / "incoming.json",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 added" in result.output
    assert "added" in result.output and "demo" in result.output

    assert (library_root / "demo" / "SKILL.md").exists()
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert "demo" in lock["skills"]
    assert lock["skills"]["demo"]["localSha"] == sha


def test_import_skips_existing_and_preserves_lock(
    installed_skill, git_sandbox, tmp_path
):
    """A slug already in the library is skipped; its lock entry is untouched."""
    before = installed_skill.lock_path.read_text()

    # Incoming names the SAME slug 'demo' but points at a different source.
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "demo": {
                "source": "someone/other-repo",
                "sourceType": "github",
                "skillPath": "SKILL.md",
                "upstreamSha": "deadbeef",
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 skipped" in result.output
    assert "already present" in result.output

    # Additive-merge invariant: existing entry byte-identical.
    assert installed_skill.lock_path.read_text() == before


def test_import_latest_clones_current_head(make_behind, tmp_path, monkeypatch):
    """--latest lands on upstream HEAD, not the recorded (older) sha."""
    from agent_toolkit_cli import skill_git
    sandbox = make_behind
    library_root = tmp_path / "lib" / "skills"
    for k, v in sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    # Recorded sha = the OLD clone HEAD (before upstream advanced).
    old_sha = skill_git.head_sha(sandbox.clone, env=None)
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "demo": {
                "source": str(sandbox.upstream),
                "sourceType": "git",
                "skillPath": "SKILL.md",
                "upstreamSha": old_sha,
                "localSha": old_sha,
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming), "--latest"])
    assert result.exit_code == 0, result.output
    assert "latest:" in result.output

    landed = skill_git.head_sha(library_root / "demo", env=None)
    assert landed != old_sha, "with --latest, HEAD should be upstream's newer commit"


def test_import_partial_failure_exit_1_but_writes_good(
    git_sandbox, tmp_path, monkeypatch
):
    from agent_toolkit_cli import skill_git
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    good_sha = skill_git.head_sha(git_sandbox.clone, env=None)
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "good": {
                "source": str(git_sandbox.upstream),
                "sourceType": "git", "skillPath": "SKILL.md",
                "upstreamSha": good_sha, "localSha": good_sha,
            },
            "bad": {
                "source": str(tmp_path / "does-not-exist.git"),
                "sourceType": "git", "skillPath": "SKILL.md",
                "upstreamSha": "deadbeef",
            },
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 1, result.output
    assert "1 added" in result.output and "1 failed" in result.output
    assert "failed" in result.output and "bad" in result.output

    # Good skill still landed and is in the lock.
    assert (library_root / "good" / "SKILL.md").exists()
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert "good" in lock["skills"]
    assert "bad" not in lock["skills"]


def test_import_reconstructs_monorepo_entry(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_update_monorepo import _init_parent
    parent = _init_parent(tmp_path)
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    # Incoming lock describes a monorepo skill: directory skillPath, parentUrl,
    # read_only. owner_repo synthesised as local/<name> by file:// parsing.
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "mkdocs": {
                "source": f"local/{parent.name}",
                "sourceType": "git",
                "skillPath": "mkdocs",
                "parentUrl": f"file://{parent}",
                "readOnly": True,
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 added" in result.output

    canonical = library_root / "mkdocs"
    assert (canonical / "SKILL.md").exists(), "monorepo skill materialised"
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert lock["skills"]["mkdocs"]["skillPath"] == "mkdocs"
    assert lock["skills"]["mkdocs"].get("readOnly") is True


def test_import_self_is_noop(installed_skill):
    """Importing the live global lock onto itself skips all, changes nothing."""
    before = installed_skill.lock_path.read_text()
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(installed_skill.lock_path)])
    assert result.exit_code == 0, result.output
    assert "0 added" in result.output
    assert "skipped" in result.output
    assert installed_skill.lock_path.read_text() == before


def test_import_appears_in_skill_help():
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "--help"])
    assert result.exit_code == 0
    assert "import" in result.output
