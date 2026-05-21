from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_tui.skill_state import SkillCell, SkillRow, build_skill_rows, _cell_for


def _add_demo_project(runner, upstream_path, project, library_root):
    """Add demo skill to library then install it at project scope for claude-code."""
    r = runner.invoke(main, ["skill", "add", str(upstream_path), "--slug", "demo"])
    if r.exit_code != 0:
        return r
    (project / ".claude").mkdir(exist_ok=True)
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo",
        "--scope", "project",
        "--agents", "claude-code",
    ])


def test_build_skill_rows_clean(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output
    rows = build_skill_rows(scope="project", home=None, project=project)
    assert any(r.slug == "demo" and r.state == "clean" for r in rows)


def test_build_skill_rows_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output
    (project / ".agents" / "skills" / "demo" / "SKILL.md").write_text("edit\n")
    rows = build_skill_rows(scope="project", home=None, project=project)
    assert rows[0].state == "dirty"


def test_build_skill_rows_empty(tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    rows = build_skill_rows(scope="global", home=tmp_path, project=None)
    assert rows == []


def test_build_skill_rows_missing_canonical(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    import shutil
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output
    # Remove the canonical dir behind the lock's back.
    shutil.rmtree(project / ".agents" / "skills" / "demo")
    rows = build_skill_rows(scope="project", home=None, project=project)
    assert rows[0].state == "missing"


# ---------------------------------------------------------------------------
# Universal cell tests
# ---------------------------------------------------------------------------

def test_universal_cell_global_not_linked(tmp_path: Path, monkeypatch):
    """At global scope, universal cell is not linked when ~/.agents/skills/<slug> is absent."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    cell = _cell_for("demo", "universal", scope="global", home=fake_home, project=None)
    assert cell == SkillCell(linked=False, drift=False, skipped=False)


def test_universal_cell_global_linked(tmp_path: Path, monkeypatch):
    """At global scope, universal cell is linked when ~/.agents/skills/<slug> → library canonical."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    # Create the library canonical.
    canonical = library_root / "demo"
    canonical.mkdir(parents=True)

    # Create the bundle link ~/.agents/skills/demo → canonical.
    bundle_dir = fake_home / ".agents" / "skills"
    bundle_dir.mkdir(parents=True)
    bundle_link = bundle_dir / "demo"
    bundle_link.symlink_to(canonical)

    # Patch Path.home() so _universal_bundle_link resolves under fake_home.
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    cell = _cell_for("demo", "universal", scope="global", home=fake_home, project=None)
    assert cell == SkillCell(linked=True, drift=False, skipped=False)


def test_universal_cell_global_drifted(tmp_path: Path, monkeypatch):
    """At global scope, universal cell is drifted when symlink points elsewhere."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    # Library canonical (where the link SHOULD point).
    canonical = library_root / "demo"
    canonical.mkdir(parents=True)

    # Some other directory (where the link ACTUALLY points).
    elsewhere = tmp_path / "elsewhere" / "demo"
    elsewhere.mkdir(parents=True)

    # Create the bundle link pointing to the wrong place.
    bundle_dir = fake_home / ".agents" / "skills"
    bundle_dir.mkdir(parents=True)
    bundle_link = bundle_dir / "demo"
    bundle_link.symlink_to(elsewhere)

    # Patch Path.home() so _universal_bundle_link resolves under fake_home.
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    cell = _cell_for("demo", "universal", scope="global", home=fake_home, project=None)
    assert cell == SkillCell(linked=False, drift=True, skipped=False)


def test_universal_cell_project_linked(tmp_path: Path, monkeypatch):
    """At project scope, universal cell is linked when the project canonical dir exists."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()

    # Create the project canonical as a real directory (not a symlink).
    canonical = project / ".agents" / "skills" / "demo"
    canonical.mkdir(parents=True)

    cell = _cell_for("demo", "universal", scope="project", home=None, project=project)
    assert cell == SkillCell(linked=True, drift=False, skipped=False)


def test_universal_cell_project_not_linked(tmp_path: Path, monkeypatch):
    """At project scope, universal cell is not linked when the project canonical is absent."""
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()

    cell = _cell_for("demo", "universal", scope="project", home=None, project=project)
    assert cell == SkillCell(linked=False, drift=False, skipped=False)


def test_universal_cell_project_symlink_not_linked(tmp_path: Path, monkeypatch):
    """At project scope, universal cell is NOT linked when the path is a symlink.

    The project canonical must be a real directory, not a symlink.  A symlink
    at that path would indicate an incorrect install; we report not-linked.
    """
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()

    # Create a symlink at the project canonical path instead of a real dir.
    target = tmp_path / "elsewhere"
    target.mkdir()
    (project / ".agents" / "skills").mkdir(parents=True)
    (project / ".agents" / "skills" / "demo").symlink_to(target)

    cell = _cell_for("demo", "universal", scope="project", home=None, project=project)
    # A symlink is not the project canonical; linked must be False.
    assert cell.linked is False


def test_build_skill_rows_includes_universal_cell(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """build_skill_rows populates a universal cell for each row."""
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="project", home=None, project=project)
    assert rows, "expected at least one row"
    row = rows[0]
    # The universal cell must be present in the cells dict.
    assert ("universal", "project") in row.cells, (
        f"universal cell missing; cells keys: {list(row.cells.keys())}"
    )
    # The project canonical exists as a real dir after install, so linked=True.
    universal_cell = row.cells[("universal", "project")]
    assert universal_cell.linked is True
    assert universal_cell.skipped is False
