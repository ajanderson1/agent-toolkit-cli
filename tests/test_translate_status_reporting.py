"""Regression tests for #40-A — bare-slug lookup misses translate cells.

`_list_json._cell_status` and `doctor/symlinks.py` both built the slot lookup
path using a bare slug. For OpenCode agents/commands the actual slot filename
is `<slug>.md`, so the lookups missed the link and reported `unlinked` /
`expected symlink missing` even when the link was healthy.

These tests exercise the bug end-to-end via the same `seed_agent` + `link user
opencode` pattern as `tests/test_cli_link.py`, then probe the two reporting
surfaces directly.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.commands._list_json import _build_inventory
from agent_toolkit_cli.doctor import symlinks as doctor_symlinks


def _link_opencode_agent(env, seed_agent, slug: str = "foo") -> dict:
    """Helper: seed an opencode-only agent, allowlist it, run `link user opencode`.

    Returns the env dict augmented with the slot/cache paths for assertions.
    """
    home: Path = env["home"]
    toolkit: Path = env["toolkit_root"]
    seed_agent(toolkit, slug, ["opencode"])
    (home / ".agent-toolkit.yaml").write_text(f"agents:\n  - {slug}\n")

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "opencode"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)

    slot = home / ".config" / "opencode" / "agents" / f"{slug}.md"
    cache = (
        home / ".config" / "opencode" / ".agent-toolkit-cache" / "agent" / f"{slug}.md"
    )
    assert slot.is_symlink(), f"link command did not produce slot {slot}"
    assert cache.is_file(), f"link command did not produce cache {cache}"

    return {**env, "slot": slot, "cache": cache, "slug": slug}


def test_list_json_finds_opencode_translated_agent(env, seed_agent):
    """`_cell_status` must report `linked` for an OpenCode-translated agent.

    History:
    - On `main` (pre-PR-A): asserted `status != "unlinked"` and FAILED
      because the bare-slug lookup missed `<slug>.md`.
    - After PR-A only: this assertion would PASS but the cell would
      report `status == "broken"` (cache target outside toolkit repo).
    - After PR-B: the inside-repo check is widened to recognise the
      per-scope cache root as a valid translate target, so the cell
      now reports `status == "linked"`.
    """
    e = _link_opencode_agent(env, seed_agent)
    inv = _build_inventory(e["toolkit_root"], project_root=Path("/nonexistent-project"))
    foo_assets = [a for a in inv["assets"] if a["slug"] == e["slug"] and a["kind"] == "agent"]
    assert len(foo_assets) == 1, f"expected one agent/{e['slug']} in inventory, got {len(foo_assets)}"
    cells = foo_assets[0]["cells"]
    cell = next(
        (c for c in cells if c["harness"] == "opencode" and c["scope"] == "user"),
        None,
    )
    assert cell is not None, "no (opencode, user) cell found"
    assert cell["status"] == "linked", (
        f"expected linked after PR-B cache-root recognition; "
        f"got status={cell['status']!r}, target={cell['target']!r}"
    )


def test_doctor_symlinks_finds_opencode_translated_agent(env, seed_agent):
    """`doctor.symlinks.run` must find the translated slot file.

    Before the fix, this asserts a warning string `"expected symlink ... missing"`
    is emitted because the lookup uses a bare slug.
    """
    e = _link_opencode_agent(env, seed_agent)
    result = doctor_symlinks.run(e["toolkit_root"], harness="opencode")

    missing = [f for f in result.findings if "expected symlink" in f and "missing" in f]
    assert not missing, (
        f"bug regression: doctor reported translated slot as missing: {missing}"
    )

    linked = [f for f in result.findings if f.startswith(f"agent/{e['slug']}: linked")]
    assert linked, (
        f"expected `agent/{e['slug']}: linked` in findings, got: {result.findings}"
    )


# Note: the stale-link sweep at doctor/symlinks.py:63-87 iterates real
# filenames (so for opencode agents it sees `foo.md`). Today this loop short-
# circuits via the `target.relative_to(toolkit_root)` check at line 70-72 —
# translated cells point into the cache dir, never into the toolkit, so the
# `declared_slugs.get((kind, entry.name))` lookup is unreachable. Stripping
# `.md` from `entry.name` would be defensive plumbing for a code path that
# isn't reached today. Defer to PR-B (which changes the cache-vs-repo target
# shape and so makes the stale-sweep `.md`-stripping load-bearing).
