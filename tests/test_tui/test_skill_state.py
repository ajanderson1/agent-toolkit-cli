from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_tui.skill_state import SkillRow, build_skill_rows


def test_build_skill_rows_clean(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    CliRunner().invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    rows = build_skill_rows(scope="global", home=fake_home, project=None)
    assert rows == [
        SkillRow(
            slug="demo",
            source=str(git_sandbox.upstream),
            ref="main",
            state="clean",
        ),
    ]


def test_build_skill_rows_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    CliRunner().invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    (fake_home / ".agents" / "skills" / "demo" / "SKILL.md").write_text("edit\n")
    rows = build_skill_rows(scope="global", home=fake_home, project=None)
    assert rows[0].state == "dirty"


def test_build_skill_rows_empty(tmp_path: Path):
    rows = build_skill_rows(scope="global", home=tmp_path, project=None)
    assert rows == []


def test_build_skill_rows_missing_canonical(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    import shutil
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    CliRunner().invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    # Remove the canonical dir behind the lock's back.
    shutil.rmtree(fake_home / ".agents" / "skills" / "demo")
    rows = build_skill_rows(scope="global", home=fake_home, project=None)
    assert rows[0].state == "missing"
