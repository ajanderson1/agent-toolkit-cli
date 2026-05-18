"""End-to-end tests for #41 — opencode skill translate uses dir-with-file-symlink layout.

OpenCode's skill discovery does NOT follow directory symlinks during the glob
walk (empirically verified against opencode 1.14.30); it does follow file
symlinks within real directories. So `(opencode, skill)` cells use a third
slot layout introduced in this PR:

  - "file":                  slot is a symlink to the cache file. (opencode agent/command)
  - "dir-symlink":           slot is a symlink to the cache directory. (codex skill)
  - "dir-with-file-symlink": slot is a real directory containing a file symlink
                             to the cache file. (opencode skill — new)

These tests exercise the new layout end-to-end via the CLI link/unlink path.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.commands._link_lib import (
    _render_to_cache,
    _translate_slot_layout,
)
from agent_toolkit_cli.commands._list_json import _build_inventory


# ---------------------------------------------------------------------------
# 1. _translate_slot_layout dispatch
# ---------------------------------------------------------------------------


def test_translate_slot_layout_opencode_skill_is_dir_with_file_symlink():
    assert _translate_slot_layout("opencode", "skill") == "dir-with-file-symlink"


def test_translate_slot_layout_codex_skill_unchanged():
    assert _translate_slot_layout("codex", "skill") == "dir-symlink"


def test_translate_slot_layout_opencode_agent_unchanged():
    assert _translate_slot_layout("opencode", "agent") == "file"


def test_translate_slot_layout_opencode_command_unchanged():
    assert _translate_slot_layout("opencode", "command") == "file"


# ---------------------------------------------------------------------------
# 2. _render_to_cache returns the cache file as slot_target (not the dir)
# ---------------------------------------------------------------------------


def test_render_to_cache_opencode_skill_targets_cache_file_not_dir(
    tmp_path, monkeypatch, seed_toolkit, seed_skill,
):
    """For dir-with-file-symlink, slot_target == cache_path (the SKILL.md
    file inside the cache slug dir), NOT cache_path.parent."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    toolkit = seed_toolkit(tmp_path)
    skill_dir = seed_skill(toolkit, "demo-skill", ["opencode"])

    cache_path, slot_target, rendered = _render_to_cache(
        harness="opencode", kind="skill", slug="demo-skill",
        asset_path=skill_dir / "SKILL.md", scope="user",
        project_root=Path("/unused-for-user-scope"),
        dry_run=False,
    )

    expected_cache_root = (
        tmp_path / "home" / ".config" / "opencode" / ".agent-toolkit-cache"
    )
    assert cache_path == expected_cache_root / "skill" / "demo-skill" / "SKILL.md"
    # slot_target is the file, not its parent dir — the slot symlink lives
    # one level deeper inside a real slot directory.
    assert slot_target == cache_path
    assert cache_path.is_file()
    # Translator output includes the top-level name + description fields opencode requires.
    assert b"name: demo-skill" in rendered
    assert b"description: demo-skill skill." in rendered


# ---------------------------------------------------------------------------
# 3. End-to-end link: real slot dir + file symlink to cache
# ---------------------------------------------------------------------------


def test_link_user_opencode_skill_creates_real_slot_dir_and_file_symlink(
    env, seed_skill,
):
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "demo-skill", ["opencode"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - demo-skill\n")

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "opencode"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)

    slot_dir = home / ".config" / "opencode" / "skills" / "demo-skill"
    slot_skill_md = slot_dir / "SKILL.md"
    cache_skill_md = (
        home / ".config" / "opencode" / ".agent-toolkit-cache"
        / "skill" / "demo-skill" / "SKILL.md"
    )

    # Slot directory is REAL (not a symlink) — opencode needs this for its
    # directory-walk glob to recurse into.
    assert slot_dir.is_dir(), f"slot dir should be a real directory: {slot_dir}"
    assert not slot_dir.is_symlink(), "slot dir should not be a symlink"

    # The actual symlink lives inside the slot directory.
    assert slot_skill_md.is_symlink(), f"SKILL.md should be a symlink: {slot_skill_md}"
    assert cache_skill_md.is_file(), f"cache file should exist: {cache_skill_md}"

    # The symlink targets the cache file.
    target = Path(os.readlink(str(slot_skill_md)))
    if not target.is_absolute():
        target = (slot_skill_md.parent / target).resolve()
    assert target == cache_skill_md

    # Reading through the slot returns the translated content (opencode's view).
    via_slot = slot_skill_md.read_text()
    assert "name: demo-skill" in via_slot
    assert "description: demo-skill skill." in via_slot
    assert "agent_toolkit_cli:" in via_slot


def test_link_user_opencode_skill_idempotent(env, seed_skill):
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "demo-skill", ["opencode"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - demo-skill\n")

    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "opencode"])
    # Second run should be a no-op (counters: unchanged).
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "opencode"],
    )
    assert result.exit_code == 0
    assert "already in sync" in result.output.lower() or "0 new" in result.output.lower()


# ---------------------------------------------------------------------------
# 4. End-to-end unlink: removes file symlink, cache content, slot dir
# ---------------------------------------------------------------------------


def test_unlink_user_opencode_skill_removes_file_symlink_and_cache_and_slot_dir(
    env, seed_skill,
):
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "demo-skill", ["opencode"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - demo-skill\n")

    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "opencode"])

    slot_dir = home / ".config" / "opencode" / "skills" / "demo-skill"
    slot_skill_md = slot_dir / "SKILL.md"
    cache_skill_md = (
        home / ".config" / "opencode" / ".agent-toolkit-cache"
        / "skill" / "demo-skill" / "SKILL.md"
    )
    cache_slug_dir = cache_skill_md.parent
    assert slot_skill_md.is_symlink() and cache_skill_md.is_file(), "preconditions"

    # Drop the slug from the allowlist, sweep with --all
    (home / ".agent-toolkit.yaml").write_text("skills:\n")
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "opencode", "--all"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)

    assert not slot_skill_md.exists(), "slot SKILL.md symlink should be gone"
    assert not slot_dir.exists(), "slot <slug>/ dir should be gone (it was empty)"
    assert not cache_skill_md.exists(), "cache SKILL.md should be gone"
    assert not cache_slug_dir.exists(), "cache <slug>/ dir should be gone"


# ---------------------------------------------------------------------------
# 5. _cell_status reports "linked" for the new layout
# ---------------------------------------------------------------------------


def test_cell_status_reports_linked_for_opencode_skill_dir_with_file_symlink(
    env, seed_skill,
):
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "demo-skill", ["opencode"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - demo-skill\n")

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "opencode"],
    )
    assert result.exit_code == 0

    inv = _build_inventory(toolkit, project_root=Path("/nonexistent-project"))
    cells = next(a for a in inv["assets"] if a["slug"] == "demo-skill")["cells"]
    cell = next(c for c in cells if c["harness"] == "opencode" and c["scope"] == "user")
    assert cell["status"] == "linked", (
        f"expected linked, got status={cell['status']!r}, target={cell['target']!r}"
    )
