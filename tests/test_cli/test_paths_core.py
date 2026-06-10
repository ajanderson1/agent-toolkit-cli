import os

from agent_toolkit_cli._paths_core import (
    AssetTypeBinding,
    SKILL_BINDING,
    library_root_for_asset_type,
    library_lock_path_for_asset_type,
)


def test_kind_binding_is_frozen_dataclass():
    b = AssetTypeBinding(
        asset_type="x",
        canonical_dirname="xs",
        library_subdir="_library/xs",
        lock_filename="xs-lock.json",
        standard_harness_name="standard-x",
    )
    import dataclasses
    assert dataclasses.is_dataclass(b)
    # Frozen — assignment should raise.
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.asset_type = "y"  # type: ignore[misc]


def test_skill_binding_is_the_canonical_skill_binding():
    assert SKILL_BINDING.asset_type == "skill"
    assert SKILL_BINDING.canonical_dirname == "skills"
    assert SKILL_BINDING.library_subdir == "skills"  # under ~/.agent-toolkit/
    assert SKILL_BINDING.lock_filename == "skills-lock.json"
    assert SKILL_BINDING.standard_harness_name == "standard-skill"


def test_library_root_for_asset_type_uses_binding_subdir(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    fake_home = tmp_path / "h"
    monkeypatch.setenv("HOME", str(fake_home))
    # The existing library_root() returns ~/.agent-toolkit/skills/. The
    # kinded helper returns ~/.agent-toolkit/<binding.library_subdir>/.
    expected = fake_home / ".agent-toolkit" / "skills"
    assert library_root_for_asset_type(SKILL_BINDING, env=dict(os.environ)) == expected


def test_library_root_for_asset_type_with_fake_asset_type(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    fake_home = tmp_path / "h"
    monkeypatch.setenv("HOME", str(fake_home))
    fake = AssetTypeBinding(
        asset_type="x", canonical_dirname="xs", library_subdir="xs",
        lock_filename="xs-lock.json", standard_harness_name="standard-x",
    )
    assert library_root_for_asset_type(fake, env=dict(os.environ)) == fake_home / ".agent-toolkit" / "xs"


def test_library_lock_path_for_asset_type(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    fake_home = tmp_path / "h"
    monkeypatch.setenv("HOME", str(fake_home))
    assert library_lock_path_for_asset_type(SKILL_BINDING, env=dict(os.environ)) \
        == fake_home / ".agent-toolkit" / "skills-lock.json"


def test_library_root_for_asset_type_skill_respects_env_override(tmp_path, monkeypatch):
    """Back-compat: $AGENT_TOOLKIT_SKILLS_ROOT must still override SKILL_BINDING."""
    custom = tmp_path / "elsewhere"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(custom))
    assert library_root_for_asset_type(SKILL_BINDING, env=dict(os.environ)) == custom
