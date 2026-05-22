"""Integration tests for `agent-toolkit-cli skill doctor`."""
from __future__ import annotations

import shutil
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _seed(runner, upstream, monkeypatch, tmp_path):
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    r = runner.invoke(main, ["skill", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    return library_root, fake_home


def test_doctor_clean_tree_exit0(git_sandbox, tmp_path: Path, monkeypatch):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    _seed(runner, git_sandbox.upstream, monkeypatch, tmp_path)
    r = runner.invoke(main, ["skill", "doctor", "-g"])
    assert r.exit_code == 0, r.output
    assert "all clean" in r.output


def test_doctor_no_flag_outside_project_uses_global(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """No flag + no project lock at cwd → doctor consults global scope (#220).

    Mirrors the #216 list/status fix for verbs that mutate / inspect.
    Without the fix, doctor reads an empty project lock and reports
    `✓ all clean` (false-clean for an installed global skill).
    """
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    # Plant drift in the GLOBAL library so a global-scope diagnose finds it.
    # If doctor (with no flag) silently goes to project scope, it will see
    # an empty lock and report `✓ all clean` — missing the global drift.
    shutil.rmtree(library_root / "demo")

    not_a_project = tmp_path / "not-a-project"
    not_a_project.mkdir()
    r = runner.invoke(main, [
        "--project", str(not_a_project), "skill", "doctor", "--no-fix",
    ])
    assert r.exit_code == 1, r.output  # findings present → non-zero
    assert "missing_canonical" in r.output
    assert "demo" in r.output


def test_doctor_no_fix_exits_nonzero_with_findings(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    shutil.rmtree(library_root / "demo")
    r = runner.invoke(main, ["skill", "doctor", "-g", "--no-fix"])
    assert r.exit_code == 1, r.output
    assert "missing_canonical" in r.output


def test_doctor_yes_fixes_drift(git_sandbox, tmp_path: Path, monkeypatch):
    from dataclasses import replace as dc_replace
    from agent_toolkit_cli import skill_agents

    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "home" / ".claude"))
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    # Patch claude-code's global_skills_dir to a path under fake_home.
    original = skill_agents.AGENTS["claude-code"]
    monkeypatch.setitem(
        skill_agents.AGENTS, "claude-code",
        dc_replace(original, global_skills_dir=fake_home / ".claude" / "skills"),
    )
    # Plant a drifted symlink within library_root so it's drift, not foreign.
    elsewhere = library_root / "elsewhere"
    elsewhere.mkdir(parents=True)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)
    # 'y' to apply the fix.
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="y\n")
    assert r.exit_code == 0, r.output
    assert stale.resolve() == (library_root / "demo").resolve()


def test_doctor_no_response_skips_and_exits_nonzero(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    from dataclasses import replace as dc_replace
    from agent_toolkit_cli import skill_agents

    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "home" / ".claude"))
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    original = skill_agents.AGENTS["claude-code"]
    monkeypatch.setitem(
        skill_agents.AGENTS, "claude-code",
        dc_replace(original, global_skills_dir=fake_home / ".claude" / "skills"),
    )
    elsewhere = library_root / "elsewhere"
    elsewhere.mkdir(parents=True)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="N\n")
    assert r.exit_code == 1, r.output
    assert stale.resolve() == elsewhere.resolve()  # untouched


def test_doctor_q_breaks_loop(git_sandbox, tmp_path: Path, monkeypatch):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    shutil.rmtree(library_root / "demo")
    r = runner.invoke(main, ["skill", "doctor", "-g"], input="q\n")
    assert r.exit_code == 1, r.output
    # Library still missing (we quit before applying).
    assert not (library_root / "demo").exists()


def test_doctor_journal_v21_to_v22_repro(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """End-to-end repro of the v2.1->v2.2 layout the user hit on `journal`.

    Setup:
      ~/.agent-toolkit/skills/journal/  - library canonical (v2.2)
      ~/.agents/skills/journal/         - real directory (v2.1 leftover)
      ~/.claude/skills/journal          - symlink to ~/.agents/skills/journal

    Expected: doctor with 'y' to all prompts ends with bundle as a symlink to
    library, claude-code link re-pointed at library, and exit code 0.
    """
    from dataclasses import replace as dc_replace
    from agent_toolkit_cli import skill_agents

    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "home" / ".claude"))
    runner = CliRunner()
    library_root, fake_home = _seed(
        runner, git_sandbox.upstream, monkeypatch, tmp_path,
    )
    # Patch every non-universal agent's global_skills_dir to a path under
    # fake_home so that real on-disk skills (e.g. ~/.pi/agent/skills/journal)
    # don't leak into the findings as foreign_symlink noise.
    for agent_name, cfg in list(skill_agents.AGENTS.items()):
        if cfg.is_universal:
            continue
        fake_dir = fake_home / f".fake-{agent_name}" / "skills"
        monkeypatch.setitem(
            skill_agents.AGENTS, agent_name,
            dc_replace(cfg, global_skills_dir=fake_dir),
        )
    # Re-patch claude-code specifically to the expected path so the
    # claude_link we plant below is actually checked by the doctor.
    original = skill_agents.AGENTS["claude-code"]
    monkeypatch.setitem(
        skill_agents.AGENTS, "claude-code",
        dc_replace(original, global_skills_dir=fake_home / ".claude" / "skills"),
    )

    # Mirror the user's actual filesystem:
    # 1. Real dir at the bundle path.
    bundle = fake_home / ".agents" / "skills" / "journal"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("v2.1 leftover\n")
    # 2. Claude link pointing at the bundle (not library).
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    claude_link = claude_skills / "journal"
    claude_link.symlink_to(bundle)
    # 3. Add a 'journal' entry to the library by reusing the demo upstream
    #    under a journal slug.
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "journal",
    ])
    assert r.exit_code == 0, r.output
    library_journal = library_root / "journal"
    assert library_journal.exists()

    # The engine diagnoses two findings:
    #   1. drifted_symlink (fixable): the claude link points at the v2.1
    #      bundle path (~/.agents/skills/journal). The new
    #      _is_universal_bundle_target predicate triggers drift instead
    #      of foreign_symlink, so this is now a prompted fix rather than
    #      a skipped report.
    #   2. wrong_type_bundle (fixable): bundle is a real dir, not a symlink.
    # Two 'y' answers apply both fixes. Exit code is 0 — nothing skipped.
    r = runner.invoke(
        main, ["skill", "doctor", "journal", "-g"], input="y\ny\n",
    )
    assert r.exit_code == 0, r.output
    assert "drifted_symlink" in r.output
    assert "wrong_type_bundle" in r.output
    assert "fixed." in r.output
    assert "foreign_symlink" not in r.output

    # Bundle is now a symlink to library.
    assert bundle.is_symlink()
    assert bundle.resolve() == library_journal.resolve()
    # Claude link resolves transitively through bundle → library.
    assert claude_link.resolve() == library_journal.resolve()
    # Backup of the original bundle dir was created.
    assert any(bundle.parent.glob("journal.bak-doctor-*"))
