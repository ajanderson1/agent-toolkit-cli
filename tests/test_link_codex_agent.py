"""Integration tests for (codex, agent) link / unlink / drift — #140.

Structure mirrors test_translate_directory_slots.py (codex/skill) and
test_translate_status_reporting.py (opencode/agent).
"""
from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.commands._link_lib import _render_to_cache
from agent_toolkit_cli.commands._list_json import _build_inventory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slot(home: Path, slug: str) -> Path:
    """User-scope slot: ~/.codex/agents/<slug>.toml"""
    return home / ".codex" / "agents" / f"{slug}.toml"


def _project_slot(project: Path, slug: str) -> Path:
    """Project-scope slot: <project>/.codex/agents/<slug>.toml"""
    return project / ".codex" / "agents" / f"{slug}.toml"


def _cache_file(home: Path, slug: str) -> Path:
    """User-scope cache: ~/.codex/.agent-toolkit-cache/agent/<slug>.toml"""
    return home / ".codex" / ".agent-toolkit-cache" / "agent" / f"{slug}.toml"


def _project_cache(project: Path, slug: str) -> Path:
    """Project-scope cache: <project>/.codex/.agent-toolkit-cache/agent/<slug>.toml"""
    return project / ".codex" / ".agent-toolkit-cache" / "agent" / f"{slug}.toml"


# ---------------------------------------------------------------------------
# 1. render_to_cache — unit-level shape check
# ---------------------------------------------------------------------------


def test_render_to_cache_codex_agent_returns_toml_file_slot(
    tmp_path, monkeypatch, seed_toolkit, seed_agent,
):
    """_render_to_cache for (codex, agent) must return a .toml cache file whose
    slot_target equals cache_path (file-slot, not directory-slot)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    toolkit = seed_toolkit(tmp_path)
    asset_path = seed_agent(toolkit, "my-agent", ["codex"])

    cache_path, slot_target, rendered = _render_to_cache(
        harness="codex", kind="agent", slug="my-agent",
        asset_path=asset_path, scope="user",
        project_root=Path("/unused"),
        dry_run=False,
    )

    expected_cache = (
        tmp_path / "home" / ".codex" / ".agent-toolkit-cache" / "agent" / "my-agent.toml"
    )
    assert cache_path == expected_cache
    assert slot_target == cache_path  # file-slot
    assert cache_path.is_file()

    # Rendered bytes must be valid TOML with the three required fields.
    parsed = tomllib.loads(rendered.decode("utf-8"))
    assert parsed["name"] == "my-agent"
    assert "description" in parsed
    assert "developer_instructions" in parsed


# ---------------------------------------------------------------------------
# 2. Link — user scope
# ---------------------------------------------------------------------------


def test_link_user_scope_creates_toml_symlink(env, seed_agent):
    """link user codex creates ~/.codex/agents/<slug>.toml → cache file."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_agent(toolkit, "my-agent", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("agents:\n  - my-agent\n")

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"],
    )
    assert result.exit_code == 0, result.output

    slot = _slot(home, "my-agent")
    cache = _cache_file(home, "my-agent")

    assert slot.is_symlink(), f"slot {slot} should be a symlink"
    assert cache.is_file(), f"cache {cache} should exist"

    # Slot symlink must point at the cache file.
    target = Path(os.readlink(str(slot)))
    if not target.is_absolute():
        target = (slot.parent / target).resolve()
    assert target == cache.resolve()


def test_link_user_scope_cache_is_valid_toml_with_required_fields(env, seed_agent):
    """The rendered cache file must be valid TOML with name, description,
    developer_instructions, and [agent_toolkit_cli] wrapper."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_agent(toolkit, "my-agent", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("agents:\n  - my-agent\n")

    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"])

    cache = _cache_file(home, "my-agent")
    parsed = tomllib.loads(cache.read_bytes().decode("utf-8"))

    assert parsed["name"] == "my-agent"
    assert parsed["description"] == "my-agent agent."  # from conftest AGENT_FRONTMATTER
    assert "developer_instructions" in parsed
    assert "agent_toolkit_cli" in parsed
    assert parsed["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"
    meta = json.loads(parsed["agent_toolkit_cli"]["metadata"])
    assert meta["name"] == "my-agent"


# ---------------------------------------------------------------------------
# 3. Link — project scope
# ---------------------------------------------------------------------------


def test_link_project_scope_creates_toml_symlink(env, tmp_path, seed_agent):
    """link project codex creates <project>/.codex/agents/<slug>.toml → cache."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_agent(toolkit, "my-agent", ["codex"])

    project = tmp_path / "myproject"
    project.mkdir()
    allowlist = project / ".agent-toolkit.yaml"
    allowlist.write_text("agents:\n  - my-agent\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--toolkit-repo", str(toolkit),
            "link", "project", "codex",
            "--project", str(project),
        ],
    )
    assert result.exit_code == 0, result.output

    slot = _project_slot(project, "my-agent")
    cache = _project_cache(project, "my-agent")

    assert slot.is_symlink(), f"slot {slot} should be a symlink"
    assert cache.is_file(), f"cache {cache} should exist"

    parsed = tomllib.loads(cache.read_bytes().decode("utf-8"))
    assert parsed["name"] == "my-agent"


# ---------------------------------------------------------------------------
# 4. Drift — cache hand-edit triggers rewrite on re-link
# ---------------------------------------------------------------------------


def test_drift_rewrites_cache_on_relink(env, seed_agent):
    """Hand-editing the cache TOML triggers a rewrite on the next link."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_agent(toolkit, "my-agent", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("agents:\n  - my-agent\n")

    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"])

    cache = _cache_file(home, "my-agent")
    original = cache.read_bytes()

    # Corrupt the cache: replace developer_instructions with garbage.
    drifted = original.replace(b"my-agent agent", b"CORRUPTED")
    cache.write_bytes(drifted)
    assert cache.read_bytes() != original

    # Re-link must detect drift and restore.
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"])
    restored = cache.read_bytes()
    assert restored == original, "cache was not restored after drift"


# ---------------------------------------------------------------------------
# 5. Unlink — removes slot symlink and cache file
# ---------------------------------------------------------------------------


def test_unlink_removes_slot_and_cache(env, seed_agent):
    """Unlinking a codex agent removes both the slot symlink and the cache file."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_agent(toolkit, "my-agent", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("agents:\n  - my-agent\n")

    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"])

    slot = _slot(home, "my-agent")
    cache = _cache_file(home, "my-agent")
    assert slot.is_symlink() and cache.is_file(), "preconditions"

    # Remove from allowlist then sweep.
    (home / ".agent-toolkit.yaml").write_text("agents:\n")
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "unlink", "user", "codex", "--all"],
    )
    assert result.exit_code == 0, result.output

    assert not slot.exists() and not slot.is_symlink(), "slot should be gone"
    assert not cache.exists(), "cache file should be gone"


# ---------------------------------------------------------------------------
# 6. Inventory status — "linked" after a successful link
# ---------------------------------------------------------------------------


def test_inventory_reports_linked_after_link(env, seed_agent):
    """After link, _build_inventory must report status=linked for (codex, user)."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_agent(toolkit, "my-agent", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("agents:\n  - my-agent\n")

    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"])

    inv = _build_inventory(toolkit, project_root=Path("/nonexistent-project"))
    asset_cells = next(a for a in inv["assets"] if a["slug"] == "my-agent")["cells"]
    cell = next(c for c in asset_cells if c["harness"] == "codex" and c["scope"] == "user")
    assert cell["status"] in {"linked", "linked-matches"}, (
        f"expected linked/linked-matches, got status={cell['status']!r}"
    )
