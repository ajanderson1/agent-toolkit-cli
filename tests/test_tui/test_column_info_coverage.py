"""Every rendered ⓘ resolves, and every explainable column carries ⓘ (#479 R2)."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.column_info import get_column_info, registered_pairs

# (asset_type, scope) -> the harness/meta columns the grid renders.
# Derived in Task 0; pinned here so composition changes fail loudly rather than
# silently dropping a panel.
EXPECTED = {
    ("skill", "global"): ("standard", "claude-code", "hermes-agent", "paperclip", "pi", "state"),
    ("skill", "project"): ("standard", "claude-code", "hermes-agent", "paperclip", "pi", "state"),
    ("instruction", "global"): ("standard", "claude-code", "gemini-cli"),
    ("instruction", "project"): ("standard", "claude-code", "gemini-cli"),
    ("agent", "global"): ("standard", "gemini-cli", "opencode", "pi", "state"),
    ("agent", "project"): ("standard", "gemini-cli", "opencode", "pi", "state"),
    ("mcp", "global"): ("claude-code", "codex", "opencode", "pi", "state"),
    ("mcp", "project"): ("standard", "codex", "opencode", "state"),
    ("command", "global"): ("claude-code", "codex", "gemini-cli", "pi", "state"),
    ("command", "project"): ("claude-code", "codex", "gemini-cli", "pi", "state"),
    ("pi-extension", "global"): ("pi", "origin"),
    ("pi-extension", "project"): ("pi", "origin"),
}


@pytest.mark.parametrize(("key", "columns"), sorted(EXPECTED.items()))
def test_every_rendered_column_has_info(key: tuple[str, str], columns: tuple[str, ...]) -> None:
    asset_type, scope = key
    for column in columns:
        info = get_column_info(column, asset_type=asset_type, context={"scope": scope})
        assert info.title.strip(), f"{asset_type}/{scope}/{column}: empty title"
        assert info.lines, f"{asset_type}/{scope}/{column}: empty body"


def test_unregistered_pair_is_loud() -> None:
    """A new column must fail loudly, not silently render a dead ⓘ (#479 R4)."""
    with pytest.raises(KeyError):
        get_column_info("nonsense", asset_type="skill", context={"scope": "global"})


def test_no_orphan_registry_entries() -> None:
    """Every registered pair is rendered somewhere (#193's orphan-machinery lesson)."""
    rendered = {(asset_type, column) for (asset_type, _scope), columns in EXPECTED.items() for column in columns}
    orphans = {(asset_type, column) for asset_type, column in registered_pairs() if (asset_type, column) not in rendered}
    assert not orphans, f"registry has entries no grid renders: {sorted(orphans)}"
