from pathlib import Path

import pytest

from agent_toolkit_cli.skill_install import InstallError, install, uninstall
from agent_toolkit_cli.skill_source import parse_source


def test_install_creates_canonical_and_symlinks(git_sandbox, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(
        parsed=src, slug="demo", scope="global",
        home=home, project=None, harnesses=("claude", "codex"),
        env=git_sandbox.env,
    )
    canonical = home / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()
    claude = home / ".claude" / "skills" / "demo"
    codex = home / ".codex" / "skills" / "demo"
    assert claude.is_symlink() and Path(claude.resolve()) == canonical.resolve()
    assert codex.is_symlink() and Path(codex.resolve()) == canonical.resolve()


def test_install_is_idempotent(git_sandbox, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(parsed=src, slug="demo", scope="global", home=home, project=None,
            harnesses=("claude",), env=git_sandbox.env)
    install(parsed=src, slug="demo", scope="global", home=home, project=None,
            harnesses=("claude",), env=git_sandbox.env)
    canonical = home / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()


def test_install_refuses_to_overwrite_unrelated_symlink(git_sandbox, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    claude = home / ".claude" / "skills"
    claude.mkdir(parents=True)
    (claude / "demo").symlink_to(foreign)
    src = parse_source(str(git_sandbox.upstream))
    with pytest.raises(InstallError, match="conflicting symlink"):
        install(
            parsed=src, slug="demo", scope="global",
            home=home, project=None, harnesses=("claude",),
            env=git_sandbox.env,
        )


def test_uninstall_removes_canonical_and_symlinks(git_sandbox, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(
        parsed=src, slug="demo", scope="global",
        home=home, project=None, harnesses=("claude", "codex"),
        env=git_sandbox.env,
    )
    uninstall(
        slug="demo", scope="global", home=home, project=None,
        harnesses=("claude", "codex"),
    )
    assert not (home / ".agents" / "skills" / "demo").exists()
    assert not (home / ".claude" / "skills" / "demo").exists()
    assert not (home / ".codex" / "skills" / "demo").exists()
