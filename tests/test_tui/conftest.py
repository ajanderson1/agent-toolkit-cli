"""Shared fixtures for TUI tests."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A minimal repo with a couple of skills declaring different harnesses."""
    repo = tmp_path / "repo"
    (repo / "schemas").mkdir(parents=True)
    # Copy the real schema so check works if invoked.
    real_schema = Path(__file__).resolve().parents[2] / "schemas" / "asset-frontmatter.v1alpha1.json"
    (repo / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(real_schema.read_text())

    # alpha — claude only
    (repo / "skills" / "alpha").mkdir(parents=True)
    (repo / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n  name: alpha\n  description: Alpha skill.\n  lifecycle: stable\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses:\n    - claude\n"
        "---\n"
    )
    # beta — claude + opencode
    (repo / "skills" / "beta").mkdir(parents=True)
    (repo / "skills" / "beta" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n  name: beta\n  description: Beta skill.\n  lifecycle: stable\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses:\n    - claude\n    - opencode\n"
        "---\n"
    )
    return repo


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home
