"""Tests for sidecar metadata discovery (skill + mcp)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.walker import _sidecar_path


class TestSidecarPath:
    def test_skill_sidecar_path(self, tmp_path: Path) -> None:
        result = _sidecar_path("skill", "deep-research", tmp_path)
        assert result == tmp_path / "skills" / "deep-research.toolkit.yaml"

    def test_mcp_sidecar_path(self, tmp_path: Path) -> None:
        result = _sidecar_path("mcp", "context7", tmp_path)
        assert result == tmp_path / "mcps" / "context7.toolkit.yaml"

    def test_unsupported_kind_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="sidecar not supported for kind"):
            _sidecar_path("agent", "foo", tmp_path)
