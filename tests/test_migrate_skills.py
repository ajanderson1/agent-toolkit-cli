"""migrate-skills: dry-run golden file + idempotency.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

import shutil
from pathlib import Path

from click.testing import CliRunner

# Adapt the import name based on the actual CLI module export
from agent_toolkit_cli.cli import main as cli

FIXTURE_INPUT = Path(__file__).parent / "fixtures" / "migrate_skills_input"
FIXTURE_EXPECTED = Path(__file__).parent / "fixtures" / "migrate_skills_expected"


def _copy_input(dest: Path) -> Path:
    shutil.copytree(FIXTURE_INPUT, dest)
    return dest


def test_dry_run_does_not_modify_files(tmp_path: Path):
    repo = _copy_input(tmp_path / "repo")
    runner = CliRunner()
    result = runner.invoke(cli, ["migrate-skills", "--content-repo", str(repo), "--dry-run"])
    assert result.exit_code == 0, result.output
    actual = (repo / "skills" / "example" / "SKILL.md").read_text()
    expected_input = (FIXTURE_INPUT / "skills" / "example" / "SKILL.md").read_text()
    assert actual == expected_input
    assert not (repo / "skills" / "example.toolkit.yaml").exists()


def test_run_writes_new_shape(tmp_path: Path):
    repo = _copy_input(tmp_path / "repo")
    runner = CliRunner()
    result = runner.invoke(cli, ["migrate-skills", "--content-repo", str(repo)])
    assert result.exit_code == 0, result.output

    actual_skill_md = (repo / "skills" / "example" / "SKILL.md").read_text()
    expected_skill_md = (FIXTURE_EXPECTED / "skills" / "example" / "SKILL.md").read_text()
    assert actual_skill_md == expected_skill_md

    actual_sidecar = (repo / "skills" / "example.toolkit.yaml").read_text()
    expected_sidecar = (FIXTURE_EXPECTED / "skills" / "example.toolkit.yaml").read_text()
    assert actual_sidecar == expected_sidecar


def test_idempotent_second_run(tmp_path: Path):
    repo = _copy_input(tmp_path / "repo")
    runner = CliRunner()
    runner.invoke(cli, ["migrate-skills", "--content-repo", str(repo)])
    # Snapshot after first run
    first_files = sorted(p for p in repo.rglob("*") if p.is_file())
    first = {p: p.read_bytes() for p in first_files}
    # Second run
    result = runner.invoke(cli, ["migrate-skills", "--content-repo", str(repo)])
    assert result.exit_code == 0
    assert "no skills to migrate" in result.output.lower() or "0 migrated" in result.output.lower()
    second_files = sorted(p for p in repo.rglob("*") if p.is_file())
    second = {p: p.read_bytes() for p in second_files}
    assert first == second
