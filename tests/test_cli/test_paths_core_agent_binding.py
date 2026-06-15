"""AGENT_BINDING mirrors SKILL_BINDING for the agent asset type."""
from __future__ import annotations

import dataclasses

import pytest

from agent_toolkit_cli._paths_core import (
    AGENT_BINDING,
    AssetTypeBinding,
    SKILL_BINDING,
    library_lock_path_for_asset_type,
    library_root_for_asset_type,
)


def test_agent_binding_is_an_asset_type_binding():
    assert isinstance(AGENT_BINDING, AssetTypeBinding)


def test_agent_binding_fields():
    assert AGENT_BINDING.asset_type == "agent"
    assert AGENT_BINDING.canonical_dirname == "agents"
    assert AGENT_BINDING.library_subdir == "agents"
    assert AGENT_BINDING.lock_filename == "agents-lock.json"
    assert AGENT_BINDING.standard_harness_name == "standard-agent"


def test_agent_binding_is_frozen():
    # Real check: trying to mutate raises FrozenInstanceError
    with pytest.raises(dataclasses.FrozenInstanceError):
        AGENT_BINDING.asset_type = "other"  # type: ignore[misc]


def test_library_root_for_agent_asset_type(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    root = library_root_for_asset_type(AGENT_BINDING)
    assert root == tmp_path / ".agent-toolkit" / "agents"


def test_library_lock_path_for_agent_asset_type(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = library_lock_path_for_asset_type(AGENT_BINDING)
    assert lock == tmp_path / ".agent-toolkit" / "agents-lock.json"


def test_agent_binding_distinct_from_skill(tmp_path, monkeypatch):
    """AGENT_BINDING and SKILL_BINDING must resolve to different paths."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AGENT_TOOLKIT_SKILLS_ROOT", raising=False)
    skill_root = library_root_for_asset_type(SKILL_BINDING)
    agent_root = library_root_for_asset_type(AGENT_BINDING)
    assert skill_root != agent_root
    assert skill_root.name == "skills"
    assert agent_root.name == "agents"


def test_agent_asset_type_does_not_honour_skill_root_env(tmp_path, monkeypatch):
    """AGENT_TOOLKIT_SKILLS_ROOT must NOT affect the agent library root."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", "/custom/skills/root")
    agent_root = library_root_for_asset_type(AGENT_BINDING)
    assert agent_root == tmp_path / ".agent-toolkit" / "agents"
