"""Tests for the `new` command's sidecar-default behavior."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

_SCHEMA_SRC = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"


def _setup_toolkit_root(root: Path) -> None:
    """Create the minimal structure needed for the CLI to accept a toolkit root."""
    schemas_dir = root / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    (schemas_dir / "asset-frontmatter.v1alpha2.json").write_text(_SCHEMA_SRC.read_text())
    (root / ".agent-toolkit-source").write_text("")


def _run_new(toolkit_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(toolkit_root),
         "new", *args],
        capture_output=True,
        text=True,
    )


class TestNewSkillSidecar:
    def test_new_skill_creates_sidecar_by_default(self, tmp_path: Path) -> None:
        _setup_toolkit_root(tmp_path)
        result = _run_new(tmp_path, "skill", "foo")
        assert result.returncode == 0, result.stderr
        sidecar = tmp_path / "skills" / "foo.toolkit.yaml"
        body = tmp_path / "skills" / "foo" / "SKILL.md"
        assert sidecar.exists()
        assert body.exists()
        # Body now carries harness frontmatter (name + description only, not sidecar shape)
        body_text = body.read_text()
        assert body_text.startswith("---\n")
        # Sidecar should be valid YAML with the expected shape
        meta = yaml.safe_load(sidecar.read_text())
        assert meta["apiVersion"] == "agent-toolkit/v1alpha2"
        assert meta["metadata"]["name"] == "foo"

    def test_new_skill_inline_flag_rejected(self, tmp_path: Path) -> None:
        # --inline is no longer supported for skills; skills always use the two-file shape.
        _setup_toolkit_root(tmp_path)
        result = _run_new(tmp_path, "skill", "bar", "--inline")
        assert result.returncode == 2, result.stderr
        err = result.stderr.lower()
        assert "inline" in err and "sidecar" in err, result.stderr
