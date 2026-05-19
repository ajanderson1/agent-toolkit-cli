"""Tests for sidecar metadata discovery (skill + mcp)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.walker import _sidecar_path, read_sidecar


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


class TestReadSidecar:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        result = read_sidecar(tmp_path / "skills" / "missing.toolkit.yaml")
        assert result is None

    def test_valid_yaml_returns_dict(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "foo.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: foo\n"
            "spec:\n  origin: first-party\n"
        )
        result = read_sidecar(sidecar)
        assert result == {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "foo"},
            "spec": {"origin": "first-party"},
        }

    def test_invalid_yaml_returns_none(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "broken.toolkit.yaml"
        sidecar.write_text("foo: [unclosed\n")
        result = read_sidecar(sidecar)
        assert result is None

    def test_yaml_not_a_dict_returns_none(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "list.toolkit.yaml"
        sidecar.write_text("- just\n- a\n- list\n")
        result = read_sidecar(sidecar)
        assert result is None

    def test_non_utf8_file_returns_none(self, tmp_path: Path) -> None:
        """Binary or non-UTF-8 content must not crash the caller."""
        sidecar = tmp_path / "binary.toolkit.yaml"
        sidecar.write_bytes(b"\xff\xfe\x00not-utf-8\xc3\x28")
        result = read_sidecar(sidecar)
        assert result is None
