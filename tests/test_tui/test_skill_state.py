import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_tui.skill_state import (
    INTERACTIVE_AGENTS,
    SkillCell,
    SkillRow,
    _cell_for,
    build_skill_rows,
)
from tests.conftest import scrub_git_env
from tests.test_cli.test_skill_update_monorepo import _init_parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    # Remove the project canonical behind the lock's back. Since the slug is
    # still in the library, state becomes "library" (available, not installed)
    # rather than the alarming "missing".
    shutil.rmtree(project / ".agents" / "skills" / "demo")
    rows = build_skill_rows(scope="project", home=None, project=project)
    assert rows[0].state == "library"


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


# ---------------------------------------------------------------------------
# Library-as-row-source tests (v2.2 behaviour)
# ---------------------------------------------------------------------------

def test_project_scope_shows_library_skills_before_install(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """At project scope, library slugs appear even before `skill install` is run.

    After `skill add` the library lock is populated but the project has no
    canonical. build_skill_rows must return one row per library slug with
    state="library" and all cells linked=False.
    """
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    # Only add to the library — do NOT install to the project.
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="project", home=None, project=project)
    assert len(rows) == 1, f"expected 1 row, got {len(rows)}: {[r.slug for r in rows]}"
    row = rows[0]
    assert row.slug == "demo"
    assert row.state == "library"
    for key, cell in row.cells.items():
        assert not cell.linked, (
            f"cell {key} should be unlinked before install, got linked=True"
        )


def test_cell_for_claude_code_no_claude_dir_not_skipped(tmp_path: Path, monkeypatch):
    """Project with no .claude/ → claude-code cell is linked=False, skipped=False.

    v2.2: the 'agent-root-absent' skip rule is gone. The cell shows ☐ (unlinked)
    rather than ● (skipped), meaning the user can install it.
    """
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()
    assert not (project / ".claude").exists()

    cell = _cell_for("demo", "claude-code", scope="project", home=None, project=project)
    assert cell.skipped is False
    assert cell.linked is False


def test_project_scope_universal_linked_after_install(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """At project scope, after `skill install --scope project --agents universal`,
    the universal cell is linked=True and state is 'clean'.
    """
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo",
        "--scope", "project",
        "--agents", "universal",
    ])
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="project", home=None, project=project)
    assert len(rows) == 1
    row = rows[0]
    assert row.slug == "demo"
    assert row.state == "clean"
    universal_cell = row.cells[("universal", "project")]
    assert universal_cell.linked is True


# ---------------------------------------------------------------------------
<<<<<<< HEAD
# Monorepo skill state tests (parent-clone-derived)
# ---------------------------------------------------------------------------


def _install_monorepo_skill(tmp_path: Path, monkeypatch) -> Path:
    """Bootstrap a monorepo skill at global scope. Returns the parent_clone path."""
    parent = _init_parent(tmp_path)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", f"file://{parent}", "--skill", "mkdocs"])
    assert r.exit_code == 0, r.output

    candidates = list((library / "skills" / "_parents").glob("*/*"))
    assert len(candidates) == 1, candidates
    return candidates[0]


def test_build_rows_monorepo_clean_when_parent_clean(tmp_path: Path, monkeypatch):
    _install_monorepo_skill(tmp_path, monkeypatch)
    rows = build_skill_rows(scope="global", home=tmp_path, project=None)
    row = next(r for r in rows if r.slug == "mkdocs")
    assert row.state == "clean", row


def test_build_rows_monorepo_dirty_when_parent_has_uncommitted_change(
    tmp_path: Path, monkeypatch,
):
    parent_clone = _install_monorepo_skill(tmp_path, monkeypatch)
    (parent_clone / "mkdocs" / "SKILL.md").write_text("dirty\n")
    rows = build_skill_rows(scope="global", home=tmp_path, project=None)
    row = next(r for r in rows if r.slug == "mkdocs")
    assert row.state == "dirty", row


def test_build_rows_monorepo_clean_when_parent_has_only_committed_changes(
    tmp_path: Path, monkeypatch,
):
    """Local commits with no uncommitted changes → `clean`. Matches the
    per-skill-repo branch's behaviour (git status --porcelain doesn't surface
    ahead-of-upstream)."""
    parent_clone = _install_monorepo_skill(tmp_path, monkeypatch)
    (parent_clone / "mkdocs" / "LOCAL.md").write_text("local\n")
    env = scrub_git_env()
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local"],
    ):
        subprocess.run(cmd, cwd=parent_clone, check=True, env=env)
    rows = build_skill_rows(scope="global", home=tmp_path, project=None)
    row = next(r for r in rows if r.slug == "mkdocs")
    assert row.state == "clean", row


def test_build_rows_monorepo_copy_when_parent_missing(
    tmp_path: Path, monkeypatch,
):
    """User `rm -rf`'d _parents/ — state falls back to 'copy'."""
    import shutil

    _install_monorepo_skill(tmp_path, monkeypatch)
    library_root = tmp_path / "library" / "skills"
    parents_dir = library_root / "_parents"
    shutil.rmtree(parents_dir)

    # Canonical (symlink target) is now dangling. Make canonical existent
    # so we exercise the parent-missing branch (not the missing-canonical
    # one).
    canonical = library_root / "mkdocs"
    if canonical.is_symlink():
        canonical.unlink()
    canonical.mkdir(parents=True, exist_ok=True)

    rows = build_skill_rows(scope="global", home=tmp_path, project=None)
    row = next(r for r in rows if r.slug == "mkdocs")
    assert row.state == "copy", row
=======
# Global-cell population when in project scope (#188)
# ---------------------------------------------------------------------------


def _install_demo_globally(runner, project, library_root, *, universal: bool = True):
    """Install demo at global scope. Caller already added it to the library."""
    args = [
        "skill", "install", "demo",
        "--scope", "global",
    ]
    if universal:
        args.extend(["--agents", "universal"])
    return runner.invoke(main, args)


def test_build_skill_rows_project_scope_populates_global_cells(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """In project scope, when home is provided, each row carries both
    (agent, 'project') and (agent, 'global') cells so the SkillGrid can
    render the globally-installed indicator (#188)."""
    project = tmp_path / "proj"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    r = _add_demo_project(runner, git_sandbox.upstream, project, library_root)
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="project", home=home, project=project)
    demo = next(r for r in rows if r.slug == "demo")
    # Project cells still present (existing behaviour).
    for agent in INTERACTIVE_AGENTS:
        assert (agent, "project") in demo.cells, (
            f"project cell missing for agent {agent!r}: {demo.cells.keys()}"
        )
    # Global cells now also present (new behaviour).
    for agent in INTERACTIVE_AGENTS:
        assert (agent, "global") in demo.cells, (
            f"global cell missing for agent {agent!r}: {demo.cells.keys()}"
        )


def test_build_skill_rows_project_scope_without_home_skips_global_cells(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """Backwards-compatible path: home=None in project scope omits global
    cells. The indicator simply won't render — no exception."""
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
    demo = next(r for r in rows if r.slug == "demo")
    for agent in INTERACTIVE_AGENTS:
        assert (agent, "project") in demo.cells
        assert (agent, "global") not in demo.cells, (
            f"unexpected global cell when home=None: {demo.cells.keys()}"
        )


def test_build_skill_rows_global_scope_unchanged(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """Global-scope behaviour is unchanged: no project cells get populated."""
    home = tmp_path / "home"
    home.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output

    rows = build_skill_rows(scope="global", home=home, project=None)
    demo = next(r for r in rows if r.slug == "demo")
    for agent in INTERACTIVE_AGENTS:
        assert (agent, "global") in demo.cells
        assert (agent, "project") not in demo.cells, (
            f"unexpected project cell at global scope: {demo.cells.keys()}"
        )
>>>>>>> 2f557e4 (feat(tui): populate global cells in project scope for indicator (#188))
