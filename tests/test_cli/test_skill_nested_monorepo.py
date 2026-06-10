"""End-to-end coverage for NESTED monorepo skills.

A nested monorepo has skills two (or more) levels below the repo root, under
a named group directory that is not itself a skill:

    parent/aj-workflows/aj-flow/SKILL.md
    parent/aj-workflows/aj-issue/SKILL.md

This is AJ's `personal_skills/aj-workflows/<skill>` layout. The multi-segment
skill_path ("aj-workflows/aj-flow") must round-trip through add → install →
lock → doctor repair without anything assuming a single-segment subpath.
"""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import skill_doctor
from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli.skill_paths import canonical_skill_dir

from tests.conftest import scrub_git_env


FIXTURE = Path(__file__).parent.parent / "fixtures" / "nested_monorepo_skills"


def _make_parent_repo(tmp_path: Path) -> str:
    """Initialise the nested fixture into a git repo; return its file URL."""
    parent_src = tmp_path / "personal_skills"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = scrub_git_env()
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=parent_src, check=True, env=env,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        cwd=parent_src, check=True, env=env,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=parent_src, check=True, env=env,
    )
    return f"file://{parent_src}"


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return library


def _add_nested(runner, parent_url, subpath):
    return runner.invoke(cli, ["skill", "add", f"{parent_url}/tree/main/{subpath}"])


def test_nested_add_installs_multi_segment_subpath(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()

    result = _add_nested(runner, parent_url, "aj-workflows/aj-flow")
    assert result.exit_code == 0, result.output

    # Canonical is named by the LEAF (aj-flow), not the group dir.
    canonical = library / "skills" / "aj-flow"
    assert (canonical / "SKILL.md").read_text().startswith("---\nname: aj-flow")

    # Parent cloned once; the nested skill resolves two levels deep.
    parent_clones = list((library / "skills" / "_parents").glob("*/*"))
    assert len(parent_clones) == 1
    assert (parent_clones[0] / "aj-workflows" / "aj-flow" / "SKILL.md").exists()

    # Lock records the FULL multi-segment skill_path.
    lock = json.loads((library / "skills-lock.json").read_text())
    e = lock["skills"]["aj-flow"]
    assert e["skillPath"] == "aj-workflows/aj-flow"
    assert e["parentUrl"].endswith("/personal_skills")


def test_two_nested_siblings_share_one_parent_clone(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()

    r1 = _add_nested(runner, parent_url, "aj-workflows/aj-flow")
    assert r1.exit_code == 0, r1.output
    r2 = _add_nested(runner, parent_url, "aj-workflows/aj-issue")
    assert r2.exit_code == 0, r2.output

    parent_clones = list((library / "skills" / "_parents").glob("*/*"))
    assert len(parent_clones) == 1  # one clone shared by both siblings

    lock = json.loads((library / "skills-lock.json").read_text())
    assert lock["skills"]["aj-flow"]["skillPath"] == "aj-workflows/aj-flow"
    assert lock["skills"]["aj-issue"]["skillPath"] == "aj-workflows/aj-issue"


def test_doctor_repairs_broken_nested_canonical_by_resymlinking(
    tmp_path, monkeypatch, isolated_library,
):
    """Regression: doctor's missing_canonical repair must re-clone the PARENT
    and re-symlink parent/<skill_path>, NOT flat-clone the parent into the
    slug dir (which would leave SKILL.md two levels too deep)."""
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()

    assert _add_nested(runner, parent_url, "aj-workflows/aj-flow").exit_code == 0

    canonical = canonical_skill_dir("aj-flow", scope="global", home=None, project=None)
    parent_clones = list((library / "skills" / "_parents").glob("*/*"))
    assert len(parent_clones) == 1

    # Simulate the parent clone being deleted: canonical becomes a broken symlink.
    import shutil
    shutil.rmtree(parent_clones[0])
    assert canonical.is_symlink()
    assert not canonical.exists()  # broken — target gone

    findings = skill_doctor.diagnose(
        slugs=("aj-flow",), scope="global", home=None, project=None,
    )
    missing = [f for f in findings if f.finding_type == "missing_canonical"]
    assert len(missing) == 1, [f.finding_type for f in findings]
    assert missing[0].fix_action is not None

    missing[0].fix_action.apply()

    # After repair: canonical is a symlink resolving to the nested subpath,
    # and SKILL.md sits at the canonical root (NOT under aj-workflows/aj-flow/).
    assert canonical.is_symlink()
    assert (canonical / "SKILL.md").read_text().startswith("---\nname: aj-flow")
    assert not (canonical / "aj-workflows").exists()  # not a flat parent clone
    target = canonical.resolve()
    assert target.parent.name == "aj-workflows"
    assert target.name == "aj-flow"
