"""Regression tests for #41 — pi project paths must match pi's runtime layout.

Pi (v0.70.6, `@mariozechner/pi-coding-agent`) reads project-scope resources
from `<cwd>/.pi/{skills,extensions,prompts,themes}/` — there is no `/agent/`
infix at project scope, only at user scope (`~/.pi/agent/`). The toolkit's
project-target table previously used the user-scope convention for both
scopes, so project-scope linked resources never registered.

Source-of-truth for pi's path layout:
  /opt/homebrew/lib/node_modules/@mariozechner/pi-coding-agent/dist/core/
    package-manager.js:669-686  globalBaseDir = this.agentDir
                                projectBaseDir = join(cwd, CONFIG_DIR_NAME)
    package-manager.js:1768-1777  user/projectDirs.{extensions,skills,prompts,themes}
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit._support import slot_dir


def test_pi_project_skill_path_is_under_dot_pi(tmp_path: Path) -> None:
    """Project-scope pi skills land at `<root>/.pi/skills`, not `.pi/agent/skills`."""
    got = slot_dir("pi", "skill", "project", tmp_path)
    assert got == tmp_path / ".pi" / "skills", (
        f"pi reads project skills from <cwd>/.pi/skills (no /agent/), got {got}"
    )


def test_pi_project_pi_extension_path_is_under_dot_pi(tmp_path: Path) -> None:
    """Project-scope pi extensions land at `<root>/.pi/extensions`."""
    got = slot_dir("pi", "pi-extension", "project", tmp_path)
    assert got == tmp_path / ".pi" / "extensions", (
        f"pi reads project extensions from <cwd>/.pi/extensions, got {got}"
    )


def test_pi_user_skill_path_unchanged(tmp_path: Path, monkeypatch) -> None:
    """User-scope pi skills stay at `~/.pi/agent/skills` — pi's user layout."""
    monkeypatch.setenv("HOME", str(tmp_path))
    got = slot_dir("pi", "skill", "user", tmp_path)
    assert got == tmp_path / ".pi" / "agent" / "skills", (
        f"user-scope pi skills unchanged, got {got}"
    )


def test_pi_user_pi_extension_path_unchanged(tmp_path: Path, monkeypatch) -> None:
    """User-scope pi extensions stay at `~/.pi/agent/extensions`."""
    monkeypatch.setenv("HOME", str(tmp_path))
    got = slot_dir("pi", "pi-extension", "user", tmp_path)
    assert got == tmp_path / ".pi" / "agent" / "extensions"
