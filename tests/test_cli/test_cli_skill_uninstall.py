"""Tests for `skill uninstall` — removes symlinks, library untouched.

v2.2: `skill uninstall <slug> --agents AGENTS [--scope SCOPE]` removes
agent-visibility symlinks without touching the library canonical.
"""
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_paths import project_store_root


def _add_and_install_global_universal(runner, upstream_path, library_root, fake_home):
    """Add to library then install universal bundle at global scope."""
    r = runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo",
    ])
    if r.exit_code != 0:
        return r
    return runner.invoke(main, [
        "skill", "install", "demo", "--agents", "standard",
    ])


def test_uninstall_global_universal_removes_symlink(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill uninstall --agents universal removes ~/.agents/skills/<slug>."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    r = _add_and_install_global_universal(
        runner, git_sandbox.upstream, library_root, fake_home
    )
    assert r.exit_code == 0, r.output

    bundle_link = fake_home / ".agents" / "skills" / "demo"
    assert bundle_link.is_symlink()

    result = runner.invoke(main, [
        "skill", "uninstall", "demo", "--agents", "standard",
    ])
    assert result.exit_code == 0, result.output
    assert not bundle_link.exists(), "symlink must be removed"

    # Library canonical untouched.
    assert (library_root / "demo").exists(), "library must be untouched"


def test_uninstall_idempotent(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Uninstalling an agent that isn't installed is a no-op."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output

    # Uninstall without having installed first.
    result = runner.invoke(main, [
        "skill", "uninstall", "demo", "--agents", "standard",
    ])
    assert result.exit_code == 0, result.output


def test_uninstall_project_preserves_canonical(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill uninstall --scope project removes symlinks but preserves external canonical.

    Under the v2.9 model the project canonical lives in the external per-project
    store (project_store_root), NOT inside the project tree. Uninstall removes
    projection symlinks and the project lock entry but leaves the external
    canonical intact so dirty work survives.
    """
    library_root = tmp_path / "lib" / "skills"
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output

    # Under the new model the canonical is in the external store; the in-tree
    # path is a projection symlink (for claude-code: .claude/skills/demo).
    external_canonical = project_store_root(project) / "demo"
    claude_link = project / ".claude" / "skills" / "demo"
    assert external_canonical.is_dir(), "external canonical must exist after install"
    assert claude_link.is_symlink()

    result = runner.invoke(main, [
        "--project", str(project),
        "skill", "uninstall", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert result.exit_code == 0, result.output
    assert not claude_link.exists(), "claude-code symlink must be removed"
    # External canonical preserved — the whole point of non-destructive uninstall.
    assert external_canonical.is_dir(), "external canonical must survive uninstall"


def test_uninstall_default_includes_standard_bundle(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill uninstall with no --agents removes the standard bundle symlink.

    Load-bearing regression: the maximal default is ('standard',
    *detect_installed_agents()), NOT bare `--agents all` — which would leave the
    ~/.agents/skills/<slug> bundle orphaned because the `standard` token has
    detect_installed=False (so `all` never includes it). We pin the detected set
    to empty so the union is exactly ('standard',) and assert the bundle symlink
    is gone after a bare uninstall — proving `standard` is in the default set.
    Kept fully in the fake home (no real ~/.claude writes).
    """
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    import agent_toolkit_cli.commands.skill as skill_mod
    # Pin the union's detected-agent set to empty → maximal default == ('standard',).
    monkeypatch.setattr(skill_mod, "detect_installed_agents", lambda: ())

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "install", "demo", "--agents", "standard"])
    assert r.exit_code == 0, r.output

    bundle_link = fake_home / ".agents" / "skills" / "demo"
    assert bundle_link.is_symlink()

    # Bare uninstall — the default union must include `standard`, removing the bundle.
    result = runner.invoke(main, ["skill", "uninstall", "demo"])
    assert result.exit_code == 0, result.output
    assert not bundle_link.exists(), (
        "bare uninstall must remove the standard bundle symlink "
        "(`--agents all` alone would orphan it)"
    )
    # Library canonical untouched.
    assert (library_root / "demo").exists(), "library must be untouched"


def test_uninstall_default_includes_detected_agents(monkeypatch):
    """The maximal default unions the `standard` token with detect_installed_agents().

    Proves the per-agent half of the union at the resolution level (robust, no
    real per-agent projection dirs): with detect_installed_agents pinned to a
    set, the omitted-`--agents` target passed to the engine is
    ('standard', *that set). We intercept engine_apply, record the plan's
    remove_agents, then raise InstallError (which uninstall_cmd catches and turns
    into a clean ClickException) — so no InstallResult needs to be constructed.
    """
    import agent_toolkit_cli.commands.skill as skill_mod
    from agent_toolkit_cli.skill_install import InstallError

    captured = {}

    def _capture(plan, **kw):
        captured["remove_agents"] = plan.remove_agents
        raise InstallError("captured")  # short-circuit before any disk work

    monkeypatch.setattr(skill_mod, "detect_installed_agents",
                        lambda: ("claude-code", "cursor"))
    monkeypatch.setattr(skill_mod, "engine_apply", _capture)

    runner = CliRunner()
    # No --agents → uninstall_cmd computes ('standard', *detected) and passes it
    # to the engine as remove_agents. Slug need not exist; we only inspect the plan.
    runner.invoke(main, ["skill", "uninstall", "demo"])
    assert captured.get("remove_agents") == ("standard", "claude-code", "cursor"), (
        f"maximal default must union standard + detected; got {captured.get('remove_agents')}"
    )


def test_uninstall_project_default_includes_standard_bundle(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Bare project-scope uninstall removes the project standard bundle, canonical preserved.

    Project scope removes <project>/.agents/skills/<slug> via a distinct path
    from global. Detected agents pinned empty so the default union is
    ('standard',); proves the project standard link is removed and the external
    canonical survives (non-destructive uninstall).
    """
    from agent_toolkit_cli.skill_paths import project_store_root
    library_root = tmp_path / "lib" / "skills"
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    import agent_toolkit_cli.commands.skill as skill_mod
    monkeypatch.setattr(skill_mod, "detect_installed_agents", lambda: ())

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, [
        "--project", str(project), "skill", "install", "demo",
        "--scope", "project", "--agents", "standard",
    ])
    assert r.exit_code == 0, r.output

    proj_bundle = project / ".agents" / "skills" / "demo"
    external_canonical = project_store_root(project) / "demo"
    assert proj_bundle.is_symlink(), "project standard bundle symlink must exist after install"
    assert external_canonical.is_dir()

    # Bare project uninstall — default union ('standard',) removes the bundle link.
    result = runner.invoke(main, [
        "--project", str(project), "skill", "uninstall", "demo", "--scope", "project",
    ])
    assert result.exit_code == 0, result.output
    assert not proj_bundle.exists(), "project standard bundle symlink must be removed by default uninstall"
    # Non-destructive: external canonical survives.
    assert external_canonical.is_dir(), "external canonical must survive uninstall"
