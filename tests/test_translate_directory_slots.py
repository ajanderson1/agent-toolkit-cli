"""Tests for #40-B — directory-slot translate machinery.

Skills are directory assets (`<slug>/SKILL.md`); the Phase-3 OpenCode
translate machinery was built for single-file slots only. PR-B extends:

  - `_scope_cache_root` → per-harness lookup (codex added)
  - `_render_to_cache` → returns (cache_path, slot_target, bytes); slot_target
    is `cache_path` for file-slot kinds, `cache_path.parent` for directory-slot
    kinds (skills)
  - `maybe_link` → symlinks the slot at `slot_target`
  - `_prune_translated_slot` → cleans up directory caches
  - `_cell_status` → recognises per-scope cache root as a valid translate target

Tests use a stub `(codex, skill)` translator registered for the test's lifetime
via `monkeypatch.setitem` so PR-B remains independent of PR-C's actual codex
translator.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli._translators import TRANSLATORS, _description, _render, _wrapper_block
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.commands._link_lib import _render_to_cache, _scope_cache_root
from agent_toolkit_cli.commands._list_json import _build_inventory
from agent_toolkit_cli.walker import AssetRecord


# ---------------------------------------------------------------------------
# Stub translator and shared fixtures
# ---------------------------------------------------------------------------


def _stub_codex_skill_translator(record: AssetRecord, body: str) -> bytes:
    """Stub: PR-C will replace with the real codex/skill translator."""
    fm = {
        "description": _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)


@pytest.fixture
def codex_skill_translator(monkeypatch: pytest.MonkeyPatch):
    """Register a stub `(codex, skill)` translator for the test's lifetime."""
    monkeypatch.setitem(TRANSLATORS, ("codex", "skill"), _stub_codex_skill_translator)
    yield _stub_codex_skill_translator


# ---------------------------------------------------------------------------
# 1. _scope_cache_root — per-harness table
# ---------------------------------------------------------------------------


def test_scope_cache_root_supports_codex_user(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    got = _scope_cache_root("codex", "user", project_root=Path("/anywhere"))
    assert got == tmp_path / "home" / ".codex" / ".agent-toolkit-cache"


def test_scope_cache_root_supports_codex_project(tmp_path):
    project = tmp_path / "proj"
    got = _scope_cache_root("codex", "project", project_root=project)
    assert got == project / ".codex" / ".agent-toolkit-cache"


def test_scope_cache_root_preserves_opencode(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    got = _scope_cache_root("opencode", "user", project_root=Path("/anywhere"))
    assert got == tmp_path / "home" / ".config" / "opencode" / ".agent-toolkit-cache"


def test_scope_cache_root_unknown_harness_raises(tmp_path):
    with pytest.raises(ValueError):
        _scope_cache_root("unknown-harness", "user", project_root=tmp_path)


# ---------------------------------------------------------------------------
# 2. _render_to_cache — directory-slot return signature
# ---------------------------------------------------------------------------


def test_render_to_cache_codex_skill_returns_directory_slot_target(
    tmp_path, monkeypatch, seed_toolkit, seed_skill, codex_skill_translator,
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    toolkit = seed_toolkit(tmp_path)
    skill_dir = seed_skill(toolkit, "demo-skill", ["codex"])
    asset_path = skill_dir / "SKILL.md"

    cache_path, slot_target, rendered = _render_to_cache(
        harness="codex", kind="skill", slug="demo-skill",
        asset_path=asset_path, scope="user",
        project_root=Path("/unused-for-user-scope"),
        dry_run=False,
    )

    expected_cache_root = tmp_path / "home" / ".codex" / ".agent-toolkit-cache"
    assert cache_path == expected_cache_root / "skill" / "demo-skill" / "SKILL.md"
    assert slot_target == cache_path.parent
    assert cache_path.is_file()
    assert b"description: demo-skill skill." in rendered


def test_render_to_cache_pi_skill_returns_directory_slot_target(
    tmp_path, monkeypatch, seed_toolkit, seed_skill,
):
    """Pi skills translate through the real `_translate_pi_skill` and land in
    the pi per-scope cache as a directory slot. Sanity-check the layout end-
    to-end on a legacy-inline fixture (no sidecar) so the harness_description
    fallback through to v1alpha2 metadata.description is exercised."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    toolkit = seed_toolkit(tmp_path)
    skill_dir = seed_skill(toolkit, "demo-skill", ["pi"])
    asset_path = skill_dir / "SKILL.md"

    cache_path, slot_target, rendered = _render_to_cache(
        harness="pi", kind="skill", slug="demo-skill",
        asset_path=asset_path, scope="user",
        project_root=Path("/unused-for-user-scope"),
        dry_run=False,
    )

    expected_cache_root = tmp_path / "home" / ".pi" / "agent" / ".agent-toolkit-cache"
    assert cache_path == expected_cache_root / "skill" / "demo-skill" / "SKILL.md"
    assert slot_target == cache_path.parent
    assert cache_path.is_file()
    assert b"name: demo-skill" in rendered
    assert b"description: demo-skill skill." in rendered


def test_render_to_cache_opencode_agent_keeps_file_slot(
    tmp_path, monkeypatch, seed_toolkit, seed_agent,
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    toolkit = seed_toolkit(tmp_path)
    asset_path = seed_agent(toolkit, "foo", ["opencode"])

    cache_path, slot_target, rendered = _render_to_cache(
        harness="opencode", kind="agent", slug="foo",
        asset_path=asset_path, scope="user",
        project_root=Path("/unused"),
        dry_run=False,
    )

    expected_cache_root = (
        tmp_path / "home" / ".config" / "opencode" / ".agent-toolkit-cache"
    )
    assert cache_path == expected_cache_root / "agent" / "foo.md"
    assert slot_target == cache_path  # file-slot: slot points at the cache file
    assert cache_path.is_file()


def test_render_to_cache_dry_run_no_writes_directory_slot(
    tmp_path, monkeypatch, seed_toolkit, seed_skill, codex_skill_translator,
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    toolkit = seed_toolkit(tmp_path)
    skill_dir = seed_skill(toolkit, "demo-skill", ["codex"])

    cache_path, slot_target, rendered = _render_to_cache(
        harness="codex", kind="skill", slug="demo-skill",
        asset_path=skill_dir / "SKILL.md", scope="user",
        project_root=Path("/unused"),
        dry_run=True,
    )

    assert not cache_path.exists()
    assert not slot_target.exists()
    assert b"description:" in rendered


# ---------------------------------------------------------------------------
# 3. End-to-end: link + unlink for a (codex, skill) translate cell
# ---------------------------------------------------------------------------


def test_link_user_codex_skill_translates_and_directory_symlinks(
    env, seed_skill, codex_skill_translator,
):
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "demo-skill", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - demo-skill\n")

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)

    slot = home / ".codex" / "skills" / "demo-skill"
    cache_dir = home / ".codex" / ".agent-toolkit-cache" / "skill" / "demo-skill"
    cache_skill_md = cache_dir / "SKILL.md"

    assert slot.is_symlink(), f"slot {slot} should be a symlink"
    assert cache_skill_md.is_file(), f"cache file {cache_skill_md} should exist"

    target_resolved = Path(os.readlink(str(slot)))
    if not target_resolved.is_absolute():
        target_resolved = (slot.parent / target_resolved).resolve()
    assert target_resolved == cache_dir, (
        f"slot symlink should target the cache directory, got {target_resolved}"
    )

    # Read SKILL.md through the slot — the harness's view.
    via_slot = (slot / "SKILL.md").read_text()
    assert "description: demo-skill skill." in via_slot
    assert "agent_toolkit_cli:" in via_slot


def test_unlink_user_codex_skill_removes_slot_and_cache_directory(
    env, seed_skill, codex_skill_translator,
):
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "demo-skill", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - demo-skill\n")

    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"])

    slot = home / ".codex" / "skills" / "demo-skill"
    cache_dir = home / ".codex" / ".agent-toolkit-cache" / "skill" / "demo-skill"
    cache_parent = cache_dir.parent  # .agent-toolkit-cache/skill/
    assert slot.is_symlink() and cache_dir.is_dir(), "preconditions"

    # Drop the slug from the allowlist, sweep with --all
    (home / ".agent-toolkit.yaml").write_text("skills:\n")
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "codex", "--all"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)

    assert not slot.exists() and not slot.is_symlink(), "slot should be gone"
    assert not cache_dir.exists(), "cache <slug>/ directory should be gone"
    # The kind-level parent should still exist (it's where future translated
    # skills land); the toolkit shouldn't aggressively clean above the slug.
    # If it doesn't exist (also acceptable), that's fine — the assertion is
    # that the per-slug cleanup happened, not the parent's lifecycle.


# ---------------------------------------------------------------------------
# 4. _cell_status — translate cells now report "linked" (not "broken")
# ---------------------------------------------------------------------------


def test_cell_status_reports_linked_for_translate_cell_pointing_into_cache(
    env, seed_skill, codex_skill_translator,
):
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_skill(toolkit, "demo-skill", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - demo-skill\n")

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"],
    )
    assert result.exit_code == 0

    inv = _build_inventory(toolkit, project_root=Path("/nonexistent-project"))
    cells = next(a for a in inv["assets"] if a["slug"] == "demo-skill")["cells"]
    cell = next(c for c in cells if c["harness"] == "codex" and c["scope"] == "user")
    assert cell["status"] == "linked", (
        f"expected linked, got status={cell['status']!r}, target={cell['target']!r}"
    )
