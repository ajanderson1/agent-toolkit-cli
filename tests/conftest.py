"""Shared fixtures for tests/test_cli_*.py (link/unlink/list/diff)."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest


SKILL_FRONTMATTER = """\
---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: {slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
---
"""


def _seed_toolkit_impl(tmp: Path) -> Path:
    root = tmp / "toolkit"
    root.mkdir()
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    (root / "schemas").mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    )
    (root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    return root


def _seed_skill_impl(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"    - {h}" for h in harnesses)
    (skill_dir / "SKILL.md").write_text(
        SKILL_FRONTMATTER.format(slug=slug, harness_lines=lines)
    )
    return skill_dir


def _seed_pi_extension_impl(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    ext_dir = toolkit_root / "extensions" / slug
    ext_dir.mkdir(parents=True, exist_ok=True)
    harness_lines = "\n".join(f"    - {h}" for h in harnesses)
    (ext_dir / "extension.meta.yaml").write_text(
        f"apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n"
        f"  name: {slug}\n"
        f"  description: {slug} pi extension.\n"
        f"  lifecycle: stable\n"
        f"spec:\n"
        f"  origin: first-party\n"
        f"  vendored_via: none\n"
        f"  harnesses:\n"
        f"{harness_lines}\n"
    )
    (ext_dir / "package.json").write_text('{"name": "' + slug + '", "version": "1.0.0", "type": "module"}\n')
    (ext_dir / "index.ts").write_text("export default function (pi: any) {}\n")
    return ext_dir


@pytest.fixture
def skill_frontmatter() -> str:
    """Template for SKILL.md frontmatter; format with `slug=` and `harness_lines=`."""
    return SKILL_FRONTMATTER


@pytest.fixture
def seed_toolkit() -> Callable[[Path], Path]:
    return _seed_toolkit_impl


@pytest.fixture
def seed_skill() -> Callable[[Path, str, list[str]], Path]:
    return _seed_skill_impl


@pytest.fixture
def seed_pi_extension() -> Callable[[Path, str, list[str]], Path]:
    return _seed_pi_extension_impl


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)
    toolkit_root = _seed_toolkit_impl(tmp_path)
    return {"home": home, "toolkit_root": toolkit_root}
