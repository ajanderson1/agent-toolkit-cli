"""INSTRUCTIONS_BINDING parallels SKILL_BINDING and AGENT_BINDING."""
from __future__ import annotations

from agent_toolkit_cli._paths_core import (
    INSTRUCTIONS_BINDING,
    AssetTypeBinding,
    library_lock_path_for_asset_type,
    library_root_for_asset_type,
)


def test_instructions_binding_is_an_asset_type_binding():
    assert isinstance(INSTRUCTIONS_BINDING, AssetTypeBinding)


def test_instructions_binding_field_values():
    """The fields the catalog/library/lock layout depends on."""
    assert INSTRUCTIONS_BINDING.asset_type == "instructions"
    assert INSTRUCTIONS_BINDING.canonical_dirname == "instructions"
    assert INSTRUCTIONS_BINDING.library_subdir == "instructions"
    assert INSTRUCTIONS_BINDING.lock_filename == "instructions-lock.json"
    assert INSTRUCTIONS_BINDING.standard_harness_name == "standard-instructions"


def test_library_root_for_instructions_asset_type(monkeypatch, tmp_path):
    """Library root resolves to ~/.agent-toolkit/instructions/."""
    monkeypatch.setenv("HOME", str(tmp_path))
    root = library_root_for_asset_type(INSTRUCTIONS_BINDING)
    assert root == tmp_path / ".agent-toolkit" / "instructions"


def test_library_lock_path_for_instructions_asset_type(monkeypatch, tmp_path):
    """Lock lives at ~/.agent-toolkit/instructions-lock.json."""
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = library_lock_path_for_asset_type(INSTRUCTIONS_BINDING)
    assert lock == tmp_path / ".agent-toolkit" / "instructions-lock.json"


def test_instructions_binding_does_not_honour_skill_env_override(monkeypatch, tmp_path):
    """The SKILLS_ROOT env override is skill-specific; instructions ignores it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", "/some/other/path")
    root = library_root_for_asset_type(INSTRUCTIONS_BINDING)
    assert root == tmp_path / ".agent-toolkit" / "instructions"
