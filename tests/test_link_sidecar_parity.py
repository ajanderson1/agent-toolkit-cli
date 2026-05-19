"""Integration: sidecar-described skill projects identically to inline."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCHEMA_SRC = (
    Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
)


def _make_toolkit_root(toolkit_root: Path) -> None:
    """Seed minimal toolkit-root marker so resolve_toolkit_root accepts the path.

    Both .agent-toolkit-source AND schemas/asset-frontmatter.v1alpha2.json are
    required by _is_toolkit_repo — a bare touch() is not sufficient.
    """
    (toolkit_root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    (toolkit_root / "schemas").mkdir(exist_ok=True)
    (toolkit_root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        _SCHEMA_SRC.read_text()
    )


def _setup_with_inline(root: Path) -> None:
    skill_dir = root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: Test skill.\n  lifecycle: stable\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nBody text.\n"
    )


def _setup_with_sidecar(root: Path) -> None:
    skill_dir = root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("Body text.\n")
    (root / "skills" / "foo.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: Test skill.\n  lifecycle: stable\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
    )


def test_inventory_lists_sidecar_skill(tmp_path: Path) -> None:
    _make_toolkit_root(tmp_path)
    _setup_with_sidecar(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(tmp_path),
         "inventory", "skill"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "foo" in result.stdout


def test_inventory_output_identical_inline_vs_sidecar(tmp_path: Path) -> None:
    inline_root = tmp_path / "inline"
    sidecar_root = tmp_path / "sidecar"
    inline_root.mkdir()
    sidecar_root.mkdir()
    _make_toolkit_root(inline_root)
    _make_toolkit_root(sidecar_root)
    _setup_with_inline(inline_root)
    _setup_with_sidecar(sidecar_root)

    def _inv(root: Path) -> str:
        out = subprocess.run(
            [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(root),
             "inventory", "skill"],
            capture_output=True, text=True,
        )
        # Strip absolute paths so the comparison is portable
        return out.stdout.replace(str(root), "<ROOT>")

    inline_out = _inv(inline_root)
    sidecar_out = _inv(sidecar_root)
    # The two should be identical except for the LOCATION line, which legitimately
    # differs (one is SKILL.md, the other is foo.toolkit.yaml).
    inline_filtered = "\n".join(
        line for line in inline_out.splitlines() if not line.startswith("LOCATION")
    )
    sidecar_filtered = "\n".join(
        line for line in sidecar_out.splitlines() if not line.startswith("LOCATION")
    )
    assert inline_filtered == sidecar_filtered
