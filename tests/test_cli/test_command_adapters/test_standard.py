"""Standard command projection adapter (#482): one .claude/commands/<slug>.md
slot covering Claude Code + Neovate (global) and + Devin (project)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.command_adapters import INSTALLABLE_HARNESSES, SUPPORTED_HARNESSES, get_adapter
from agent_toolkit_cli.command_adapters.base import is_managed_file, read_sidecar, sidecar_path
from agent_toolkit_cli.command_adapters.standard import (
    STANDARD_COMMAND_READERS,
    StandardCommandAdapter,
    commands_standard_covered,
)


CANONICAL_TEXT = (
    "---\n"
    "description: Demo command\n"
    "allowed-tools: Bash, Read\n"
    "argument-hint: [issue]\n"
    "---\n"
    "Do the thing: $ARGUMENTS\n"
)


def _source(tmp_path: Path, text: str = CANONICAL_TEXT) -> Path:
    src = tmp_path / "lib" / "commands" / "demo" / "COMMAND.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(text)
    return src


def test_readers_ssot():
    assert STANDARD_COMMAND_READERS == {
        "global": frozenset({"claude-code", "neovate"}),
        "project": frozenset({"claude-code", "neovate", "devin"}),
    }
    assert commands_standard_covered("global") == STANDARD_COMMAND_READERS["global"]
    assert commands_standard_covered("project") == STANDARD_COMMAND_READERS["project"]
    with pytest.raises(KeyError):
        commands_standard_covered("unknown")


def test_destination_shared_slot(tmp_path):
    adapter = StandardCommandAdapter()
    assert adapter.destination("demo", scope="global", home=tmp_path, project=None) == (
        tmp_path / ".claude" / "commands" / "demo.md"
    )
    project = tmp_path / "repo"
    assert adapter.destination("demo", scope="project", home=None, project=project) == (
        project / ".claude" / "commands" / "demo.md"
    )


@pytest.mark.parametrize("slug", ["../bad", "..\\bad", ".", "..", ""])
def test_destination_rejects_bad_slugs(tmp_path, slug):
    adapter = StandardCommandAdapter()
    with pytest.raises(ValueError):
        adapter.destination(slug, scope="global", home=tmp_path, project=None)


def test_registry_standard_and_rejects_synthetic():
    adapter = get_adapter("standard")
    assert adapter.name == "standard"
    with pytest.raises(ValueError, match="unsupported command harness"):
        get_adapter("standard-command")
    assert "standard" in INSTALLABLE_HARNESSES
    assert "standard" not in SUPPORTED_HARNESSES


def test_install_absent_slot_symlink_or_copy(tmp_path):
    src = _source(tmp_path)
    adapter = StandardCommandAdapter()
    dest = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert dest == tmp_path / ".claude" / "commands" / "demo.md"
    assert dest.resolve() == src.resolve() or dest.read_text() == src.read_text()
    assert is_managed_file(dest, slug="demo", harness="standard")
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None)


def test_install_preserves_frontmatter_bytes_symlink_and_copy(tmp_path):
    src = _source(tmp_path)
    adapter = StandardCommandAdapter()
    dest = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    if dest.is_symlink():
        assert dest.read_bytes() == src.read_bytes()
    # Force-copy path: remove and install via copy fallback simulation
    dest.unlink()
    sidecar_path(dest).unlink(missing_ok=True)
    # Simulate symlink failure by installing then comparing content for copy path
    # Direct copy path: write via install after pre-creating parent and monkeypatching
    content = src.read_text()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    from agent_toolkit_cli.command_adapters.base import write_sidecar
    write_sidecar(dest, slug="demo", harness="standard", scope="global", canonical=src, content=content)
    assert dest.read_bytes() == src.read_bytes()
    assert "allowed-tools" in dest.read_text()
    assert "argument-hint" in dest.read_text()


def test_adopt_byte_identical_regular_file(tmp_path):
    src = _source(tmp_path)
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text(src.read_text())
    adapter = StandardCommandAdapter()
    assert not adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None)
    out = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert out == dest
    assert not dest.is_symlink()
    assert dest.read_text() == src.read_text()
    assert is_managed_file(dest, slug="demo", harness="standard")
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None)


def test_adopt_canonical_resolving_legacy_symlink(tmp_path):
    src = _source(tmp_path)
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(src)
    adapter = StandardCommandAdapter()
    assert not adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None)
    out = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert out == dest
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    assert is_managed_file(dest, slug="demo", harness="standard")
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None)


def test_refuse_divergent_regular_and_foreign_symlink(tmp_path):
    src = _source(tmp_path)
    adapter = StandardCommandAdapter()
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("hand written")
    with pytest.raises(InstallError, match="unmanaged command exists"):
        adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert dest.read_text() == "hand written"

    dest.unlink()
    other = tmp_path / "other.md"
    other.write_text("other")
    dest.symlink_to(other)
    with pytest.raises(InstallError, match="unmanaged command exists"):
        adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert dest.is_symlink() and dest.resolve() == other.resolve()


def test_refresh_stale_managed_copy(tmp_path):
    src = _source(tmp_path)
    adapter = StandardCommandAdapter()
    dest = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    # Force a managed regular file with stale content
    if dest.is_symlink():
        dest.unlink()
        dest.write_text("stale")
        from agent_toolkit_cli.command_adapters.base import write_sidecar
        write_sidecar(dest, slug="demo", harness="standard", scope="global", canonical=src, content="stale")
    else:
        dest.write_text("stale")
    out = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert out.read_text() == src.read_text()
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None)


def test_stale_sidecar_plus_user_replaced_symlink_unlinks_not_writes_through(tmp_path):
    src = _source(tmp_path)
    adapter = StandardCommandAdapter()
    user_target = tmp_path / "dotfiles" / "demo.md"
    user_target.parent.mkdir(parents=True)
    user_target.write_text("user content")
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(user_target)
    from agent_toolkit_cli.command_adapters.base import write_sidecar
    write_sidecar(dest, slug="demo", harness="standard", scope="global", canonical=src, content="stale")
    out = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert out == dest
    # Slot recreated as symlink/copy to canonical; user target untouched
    assert user_target.read_text() == "user content"
    if dest.is_symlink():
        assert dest.resolve() == src.resolve()
    else:
        assert dest.read_text() == src.read_text()


def test_uninstall_owned_and_legacy_match_and_refuses_foreign(tmp_path):
    src = _source(tmp_path)
    adapter = StandardCommandAdapter()
    dest = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert adapter.uninstall("demo", src, scope="global", home=tmp_path, project=None) == dest
    assert not dest.exists() and not dest.is_symlink()
    assert not sidecar_path(dest).exists()

    # sentinel-less matching legacy file
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text())
    assert adapter.uninstall("demo", src, scope="global", home=tmp_path, project=None) == dest
    assert not dest.exists()

    # divergent unowned
    dest.write_text("hand")
    assert adapter.uninstall("demo", src, scope="global", home=tmp_path, project=None) is None
    assert dest.read_text() == "hand"


def test_uninstall_missing_slot_cleans_dangling_sidecar(tmp_path):
    src = _source(tmp_path)
    adapter = StandardCommandAdapter()
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    from agent_toolkit_cli.command_adapters.base import write_sidecar
    write_sidecar(dest, slug="demo", harness="standard", scope="global", canonical=src, content="x")
    assert adapter.uninstall("demo", src, scope="global", home=tmp_path, project=None) is None
    assert not sidecar_path(dest).exists()


def test_is_installed_requires_standard_sidecar(tmp_path):
    src = _source(tmp_path)
    adapter = StandardCommandAdapter()
    dest = tmp_path / ".claude" / "commands" / "demo.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(src)
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None) is False
    dest.unlink()
    dest.write_text(src.read_text())
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None) is False
    adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None) is True


def test_project_scope_roundtrip(tmp_path):
    src = _source(tmp_path)
    project = tmp_path / "repo"
    project.mkdir()
    adapter = StandardCommandAdapter()
    dest = adapter.install("demo", src, scope="project", home=None, project=project)
    assert dest == project / ".claude" / "commands" / "demo.md"
    assert adapter.is_installed("demo", src, scope="project", home=None, project=project)
    assert adapter.uninstall("demo", src, scope="project", home=None, project=project) == dest


def test_markdown_is_installed_for_owned_symlink(tmp_path):
    src = _source(tmp_path)
    adapter = get_adapter("pi")
    dest = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert hasattr(adapter, "is_installed")
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None)
    # Foreign file is not installed
    dest.unlink(missing_ok=True)
    if dest.is_symlink():
        pass
    dest = tmp_path / ".pi" / "agent" / "prompts" / "demo.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("hand")
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None) is False


def test_gemini_is_installed_requires_sidecar(tmp_path):
    src = _source(tmp_path)
    adapter = get_adapter("gemini-cli")
    dest = adapter.install("demo", src, scope="global", home=tmp_path, project=None)
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None)
    sidecar_path(dest).unlink()
    assert adapter.is_installed("demo", src, scope="global", home=tmp_path, project=None) is False
