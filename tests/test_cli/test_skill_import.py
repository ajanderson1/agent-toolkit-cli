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
