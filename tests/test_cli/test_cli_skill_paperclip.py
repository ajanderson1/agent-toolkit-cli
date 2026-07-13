"""End-to-end Paperclip company projection, preflight, conflict, and uninstall."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_install import InstallError, validate_projection_context
from agent_toolkit_cli.skill_paths import agent_projection_dir, project_store_root


def _company(tmp_path):
    company = tmp_path / ".paperclip/instances/default/companies/company-123"
    company.mkdir(parents=True)
    return company


def test_projection_destination_is_company_skill_library(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    company = _company(tmp_path)
    assert agent_projection_dir(
        "paperclip", "demo", scope="project", home=None, project=company,
    ) == tmp_path / ".paperclip/instances/default/skills/company-123/demo"


@pytest.fixture
def paperclip_install(git_sandbox, tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    company = home / ".paperclip/instances/default/companies/company-123"
    company.mkdir(parents=True)
    library = tmp_path / "library/skills"
    # Apply the sandbox git identity first, then pin HOME to the Paperclip
    # company home: git_sandbox.env carries its own HOME=fake-home, so setting
    # ours afterwards is what makes ~/.paperclip detection resolve here.
    for key, value in git_sandbox.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library))
    runner = CliRunner()
    added = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert added.exit_code == 0, added.output
    projection = home / ".paperclip/instances/default/skills/company-123/demo"
    return SimpleNamespace(
        home=home,
        company=company,
        projection=projection,
        runner=runner,
    )


def test_implicit_install_projects_only_to_paperclip_company(paperclip_install):
    env = paperclip_install
    result = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert result.exit_code == 0, result.output
    assert env.projection.is_symlink()
    assert (env.company / "skills-lock.json").is_file()
    assert not (env.company / ".agents/skills/demo").exists()


def test_generic_project_refuses_before_lock_or_canonical(
    paperclip_install, tmp_path,
):
    env = paperclip_install
    project = tmp_path / "ordinary"
    project.mkdir()
    result = env.runner.invoke(main, [
        "--project", str(project), "skill", "install", "demo",
        "--scope", "project", "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "paperclip" in result.output.lower()
    assert not (project / "skills-lock.json").exists()
    assert not project_store_root(project).exists()


def test_global_paperclip_install_is_rejected_without_writes(paperclip_install):
    env = paperclip_install
    result = env.runner.invoke(main, [
        "skill", "install", "demo", "--scope", "global", "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "require project scope" in result.output
    assert not (env.home / ".paperclip/skills/demo").exists()
    assert not (env.home / ".agents/skills/demo").exists()


def test_repeated_install_is_idempotent(paperclip_install):
    env = paperclip_install
    args = [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ]
    first = env.runner.invoke(main, args)
    second = env.runner.invoke(main, args)
    assert first.exit_code == second.exit_code == 0, (first.output, second.output)
    assert env.projection.is_symlink()
    assert env.projection.resolve() == project_store_root(env.company).joinpath("demo").resolve()


def test_foreign_symlink_conflict_is_preserved(paperclip_install):
    env = paperclip_install
    foreign = env.home / "foreign-skill"
    foreign.mkdir()
    env.projection.parent.mkdir(parents=True)
    env.projection.symlink_to(foreign)
    result = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "conflicting symlink" in result.output
    assert env.projection.resolve() == foreign.resolve()
    assert not (env.company / "skills-lock.json").exists()
    assert not project_store_root(env.company).exists()


def test_real_directory_conflict_is_preserved(paperclip_install):
    env = paperclip_install
    env.projection.mkdir(parents=True)
    marker = env.projection / "keep.txt"
    marker.write_text("owned elsewhere")
    result = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "conflicting non-symlink" in result.output
    assert marker.read_text() == "owned elsewhere"
    assert not (env.company / "skills-lock.json").exists()


def test_uninstall_removes_only_owned_projection(paperclip_install):
    env = paperclip_install
    install = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert install.exit_code == 0, install.output
    canonical = env.projection.resolve()
    uninstall = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "uninstall", "demo",
        "--scope", "project", "--agents", "paperclip",
    ])
    assert uninstall.exit_code == 0, uninstall.output
    assert not env.projection.exists()
    assert canonical.exists()
    assert (env.company / "skills-lock.json").exists()


def test_uninstall_refuses_foreign_projection(paperclip_install):
    env = paperclip_install
    foreign = env.home / "foreign-skill"
    foreign.mkdir()
    env.projection.parent.mkdir(parents=True)
    env.projection.symlink_to(foreign)
    uninstall = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "uninstall", "demo",
        "--scope", "project", "--agents", "paperclip",
    ])
    assert uninstall.exit_code != 0
    assert "conflicting symlink" in uninstall.output
    assert env.projection.resolve() == foreign.resolve()


def test_global_all_ignores_context_constrained_paperclip(paperclip_install):
    # Global `--agents all` must never select the company-only Paperclip
    # harness, even though this fixture's HOME contains a ~/.paperclip tree.
    # Asserted at the resolver level so the check writes nothing into the real
    # home (a live global install would project into every detected harness).
    from agent_toolkit_cli.commands.skill import _resolve_agents

    resolved = _resolve_agents("all", "global", project=None)
    assert "paperclip" not in resolved


def test_company_list_filter_reads_paperclip_projection(paperclip_install):
    env = paperclip_install
    assert env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ]).exit_code == 0
    listed = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "list", "-p",
        "--agent", "paperclip", "--json",
    ])
    assert listed.exit_code == 0, listed.output
    assert '"slug": "demo"' in listed.output


def test_generic_project_plan_and_doctor_skip_unavailable_paperclip(
    paperclip_install, tmp_path,
):
    env = paperclip_install
    project = tmp_path / "ordinary"
    project.mkdir()
    listed = env.runner.invoke(main, [
        "--project", str(project), "skill", "list", "-p", "--json",
    ])
    doctor = env.runner.invoke(main, [
        "--project", str(project), "skill", "doctor", "-p",
    ])
    assert listed.exit_code == 0, listed.output
    assert doctor.exit_code == 0, doctor.output


def test_doctor_finds_stray_company_projection(paperclip_install):
    env = paperclip_install
    stray = env.projection.parent / "stray"
    target = env.home / "stray-target"
    target.mkdir()
    stray.parent.mkdir(parents=True)
    stray.symlink_to(target)
    doctor = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "doctor", "-p",
    ])
    assert doctor.exit_code != 0
    assert "stray" in doctor.output
    assert stray.is_symlink()


@pytest.mark.parametrize(
    "slug", ["", ".", "..", "../escape", "nested/escape", "/tmp/escape"],
)
def test_engine_rejects_non_leaf_paperclip_slugs_before_writes(
    paperclip_install, slug,
):
    env = paperclip_install
    with pytest.raises(InstallError, match="one non-empty leaf name"):
        validate_projection_context(
            slug=slug,
            target_agents=(name for name in ("paperclip",)),
            scope="project",
            home=None,
            project=env.company,
        )
    assert not (env.company / "skills-lock.json").exists()


def test_symlinked_skills_parent_is_rejected(paperclip_install):
    env = paperclip_install
    skills = env.home / ".paperclip/instances/default/skills"
    redirected = env.home / "redirected"
    redirected.mkdir()
    skills.parent.mkdir(parents=True, exist_ok=True)
    skills.symlink_to(redirected)
    result = env.runner.invoke(main, [
        "--project", str(env.company), "skill", "install", "demo",
        "--agents", "paperclip",
    ])
    assert result.exit_code != 0
    assert "symlinked projection parent" in result.output
    assert not (redirected / "company-123/demo").exists()
