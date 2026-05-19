from io import StringIO
from pathlib import Path

import pytest

from agent_toolkit_cli.commands._link_lib import (
    ALL_HARNESSES,
    MALFORMED,
    LinkCounters,
    format_summary,
    iter_plan_lines,
    maybe_link,
    validate_harness,
)


def test_counters_default_zero():
    c = LinkCounters()
    assert c.created == 0
    assert c.updated == 0
    assert c.removed == 0
    assert c.unchanged == 0
    assert c.would_link == 0
    assert c.would_unlink == 0


def test_counters_summary_dry_run_no_changes():
    c = LinkCounters()
    assert format_summary(c, dry_run=True) == "Nothing to change."


def test_counters_summary_dry_run_with_changes():
    c = LinkCounters(would_link=2, would_unlink=1)
    assert format_summary(c, dry_run=True) == (
        "3 changes pending (2 to link, 1 to remove). Re-run without --dry-run to apply."
    )


def test_counters_summary_real_run_already_in_sync():
    c = LinkCounters(unchanged=5)
    assert format_summary(c, dry_run=False) == (
        "Already in sync — 5 assets linked, nothing to change."
    )


def test_counters_summary_real_run_with_changes():
    c = LinkCounters(created=3, updated=1, removed=2, unchanged=4)
    assert format_summary(c, dry_run=False) == (
        "Linked 3 new, updated 1, removed 2 stale (4 already in sync)."
    )


def test_iter_plan_lines_skips_blanks_and_comments():
    text = "\n# leading comment\nskill:alpha\n\nskill:beta # trailing\n# tail\n"
    pairs = list(iter_plan_lines(text))
    assert pairs == [("skill", "alpha"), ("skill", "beta")]


def test_iter_plan_lines_yields_malformed_marker_for_bad_line():
    pairs = list(iter_plan_lines("garbage-no-colon\nskill:alpha\n"))
    assert pairs[0] == (MALFORMED, "garbage-no-colon")
    assert pairs[1] == ("skill", "alpha")


@pytest.mark.parametrize("harness", ALL_HARNESSES)
def test_validate_harness_accepts_known(harness):
    import click

    ctx = click.Context(click.Command("noop"))
    validate_harness(ctx, harness)  # must not raise / exit


def test_validate_harness_rejects_unknown_with_message(capsys):
    import click

    ctx = click.Context(click.Command("noop"))
    with pytest.raises(click.exceptions.Exit) as exc:
        validate_harness(ctx, "banana")
    assert exc.value.exit_code == 2
    captured = capsys.readouterr()
    assert "unknown harness 'banana'" in captured.err
    for h in ALL_HARNESSES:
        assert h in captured.err


# ===========================================================================
# Issue #13 — harness_home_path helper
# ===========================================================================


def test_harness_home_path_uses_home_env(monkeypatch, tmp_path):
    from agent_toolkit_cli.commands._link_lib import harness_home_path

    monkeypatch.setenv("HOME", str(tmp_path))
    assert harness_home_path("claude") == tmp_path / ".claude"
    assert harness_home_path("pi") == tmp_path / ".pi"


def test_harness_home_path_explicit_home_overrides_env(tmp_path):
    from pathlib import Path as _P
    from agent_toolkit_cli.commands._link_lib import harness_home_path

    other = tmp_path / "other-home"
    assert harness_home_path("codex", home=other) == other / ".codex"
    assert harness_home_path("opencode", home=_P("/tmp/x")) == _P("/tmp/x/.config/opencode")


def test_project_from_file_codex_mcp_dispatches_to_adapter(tmp_path, monkeypatch):
    """Codex + allow-listed MCP → adapter writes target file."""
    import io

    from agent_toolkit_cli.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".codex").mkdir(parents=True)

    toolkit_root = tmp_path / "toolkit"
    mcp_dir = toolkit_root / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        "    - codex\n"
        "  mcp:\n"
        "    transport: stdio\n"
        "    install_method: npx\n"
        "---\n"
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    allowlist.write_text("mcps:\n  - context7\n")

    counters = LinkCounters()
    buf = io.StringIO()
    project_from_file(
        scope="user", harness="codex", toolkit_root=toolkit_root,
        project_root=project_root, allowlist_path=allowlist,
        dry_run=False, counters=counters, stdout=buf,
    )

    out = buf.getvalue()
    assert "→ creating" in out
    assert "✓ created" in out
    target = tmp_path / "home" / ".codex" / "config.toml"
    assert target.is_file()
    assert "[mcp_servers.context7]" in target.read_text()


def test_project_from_file_pi_mcp_skips_loudly(tmp_path, monkeypatch):
    """Pi + allow-listed MCP → loud skip, exit clean, no file written.

    Pi remains UnimplementedAdapter (Pi has no MCP support by design).
    """
    import io

    from agent_toolkit_cli.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(parents=True)

    toolkit_root = tmp_path / "toolkit"
    mcp_dir = toolkit_root / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        "    - pi\n"
        "  mcp:\n"
        "    transport: stdio\n"
        "    install_method: npx\n"
        "---\n"
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    allowlist.write_text("mcps:\n  - context7\n")

    counters = LinkCounters()
    buf = io.StringIO()
    project_from_file(
        scope="user", harness="pi", toolkit_root=toolkit_root,
        project_root=project_root, allowlist_path=allowlist,
        dry_run=False, counters=counters, stdout=buf,
    )

    out = buf.getvalue()
    assert "no MCP adapter for harness pi yet — skipping" in out
    assert counters.created == 0


# ===========================================================================
# Issue #30 — UnsupportedPair on direct apply
# ===========================================================================


def test_maybe_link_raises_unsupported_pair_for_codex_agent(tmp_path):
    """maybe_link must refuse an unsupported (harness, kind) loudly."""
    from agent_toolkit_cli._support import UnsupportedPair
    from agent_toolkit_cli.commands._link_lib import LinkCounters, maybe_link

    asset_path = tmp_path / "agent.md"
    asset_path.write_text("---\nspec:\n  harnesses: [codex]\n---\nbody\n")
    target = tmp_path / "target"
    target.mkdir()
    counters = LinkCounters()
    import io

    with pytest.raises(UnsupportedPair) as exc:
        maybe_link(
            harness="codex",
            kind="agent",
            slug="foo",
            asset_path=asset_path,
            target_dir=target,
            toolkit_root=tmp_path,
            dry_run=True,
            counters=counters,
            stdout=io.StringIO(),
        )
    assert exc.value.harness == "codex"
    assert exc.value.kind == "agent"


def test_project_from_file_skips_unsupported_kinds_silently(tmp_path, monkeypatch):
    """project_from_file iterates only supported kinds for the given (harness, scope).

    Pin: an agent asset declaring `codex` is allow-listed; running
    project_from_file with harness=codex must NOT touch it (codex/agent
    is unsupported at every scope). Removing the per-scope is_supported
    filter would surface the pair to harness_target_dir → None →
    RuntimeError; the filter is the only reason this test passes silently.
    """
    import io
    from agent_toolkit_cli.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path))
    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist_path = project_root / ".agent-toolkit.yaml"
    allowlist_path.write_text("agents: [foo-agent]\n")

    # Build a one-asset toolkit: agents/foo-agent.md declaring [codex].
    toolkit_root = tmp_path / "toolkit"
    agents_dir = toolkit_root / "agents"
    agents_dir.mkdir(parents=True)
    asset_path = agents_dir / "foo-agent.md"
    asset_path.write_text(
        "---\n"
        "kind: agent\n"
        "slug: foo-agent\n"
        "spec:\n"
        "  harnesses: [codex]\n"
        "---\n"
        "body\n"
    )

    counters = LinkCounters()
    out = io.StringIO()

    project_from_file(
        scope="project",
        harness="codex",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist_path,
        dry_run=True,
        counters=counters,
        stdout=out,
    )
    # The per-scope is_supported filter (#49) is the line that prevents the
    # loop from reaching harness_target_dir(codex, agent, ...) → None →
    # RuntimeError.
    assert counters.created == 0
    assert counters.removed == 0
    assert counters.would_link == 0
    assert counters.would_unlink == 0


def test_project_from_file_links_pi_agent_at_project_scope_dual_write(tmp_path, monkeypatch):
    """#75: pi/agent at project scope dual-writes to `.pi/agents/` AND `.agents/`.

    Previously (issue #49 era) pi/agent at project scope was a clean no-op
    because pi core didn't load agents. The `pi-subagents` third-party
    extension DOES load them, and reads both paths — so dual-write is now
    the right behaviour.
    """
    import io
    from agent_toolkit_cli.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path))
    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist_path = project_root / ".agent-toolkit.yaml"
    allowlist_path.write_text("agents: [foo-agent]\n")

    toolkit_root = tmp_path / "toolkit"
    agents_dir = toolkit_root / "agents"
    agents_dir.mkdir(parents=True)
    asset_path = agents_dir / "foo-agent.md"
    asset_path.write_text(
        "---\n"
        "kind: agent\n"
        "slug: foo-agent\n"
        "spec:\n"
        "  harnesses: [pi]\n"
        "---\n"
        "body\n"
    )

    counters = LinkCounters()
    out = io.StringIO()

    project_from_file(
        scope="project",
        harness="pi",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist_path,
        dry_run=True,
        counters=counters,
        stdout=out,
    )
    # Dry-run: would-link reports BOTH paths (one for `.pi/agents/`, one for `.agents/`).
    assert counters.would_link == 2
    assert counters.created == 0
    assert counters.removed == 0
    assert counters.would_unlink == 0


def test_pi_agent_user_scope_creates_symlinks_in_both_slots(tmp_path, monkeypatch):
    """#75: real (non-dry-run) link at user scope creates symlinks in BOTH
    `~/.pi/agent/agents/` and `~/.agents/` pointing at the same source.
    Verifies end-to-end dual-write."""
    import io
    from agent_toolkit_cli.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path))
    toolkit_root = tmp_path / "toolkit"
    agents_dir = toolkit_root / "agents"
    agents_dir.mkdir(parents=True)
    asset = agents_dir / "dual-test.md"
    asset.write_text(
        "---\n"
        "kind: agent\n"
        "slug: dual-test\n"
        "spec:\n"
        "  harnesses: [pi]\n"
        "---\n"
        "body\n"
    )
    allowlist = tmp_path / ".agent-toolkit.yaml"
    allowlist.write_text("agents: [dual-test]\n")

    counters = LinkCounters()
    project_from_file(
        scope="user",
        harness="pi",
        toolkit_root=toolkit_root,
        project_root=tmp_path,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=io.StringIO(),
    )
    # Pi/agent is non-translated → slot filename is the bare slug.
    primary = tmp_path / ".pi" / "agent" / "agents" / "dual-test"
    alias = tmp_path / ".agents" / "dual-test"
    assert primary.is_symlink()
    assert alias.is_symlink()
    # Both resolve to the same source asset
    assert primary.resolve() == asset.resolve()
    assert alias.resolve() == asset.resolve()


def test_pi_agent_user_scope_unlink_clears_both_slots(tmp_path, monkeypatch):
    """#75: unlink-via-reproject (removing slug from allowlist) removes BOTH
    the primary and alias symlinks."""
    import io
    from agent_toolkit_cli.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path))
    toolkit_root = tmp_path / "toolkit"
    agents_dir = toolkit_root / "agents"
    agents_dir.mkdir(parents=True)
    asset = agents_dir / "tmp-agent.md"
    asset.write_text(
        "---\n"
        "kind: agent\n"
        "slug: tmp-agent\n"
        "spec:\n"
        "  harnesses: [pi]\n"
        "---\n"
        "body\n"
    )
    allowlist = tmp_path / ".agent-toolkit.yaml"
    allowlist.write_text("agents: [tmp-agent]\n")

    counters = LinkCounters()
    project_from_file(
        scope="user", harness="pi",
        toolkit_root=toolkit_root, project_root=tmp_path,
        allowlist_path=allowlist, dry_run=False,
        counters=counters, stdout=io.StringIO(),
    )
    primary = tmp_path / ".pi" / "agent" / "agents" / "tmp-agent"
    alias = tmp_path / ".agents" / "tmp-agent"
    assert primary.is_symlink() and alias.is_symlink()

    # Remove from allowlist + re-project — both symlinks should be pruned.
    allowlist.write_text("agents: []\n")
    counters2 = LinkCounters()
    project_from_file(
        scope="user", harness="pi",
        toolkit_root=toolkit_root, project_root=tmp_path,
        allowlist_path=allowlist, dry_run=False,
        counters=counters2, stdout=io.StringIO(),
    )
    assert not primary.exists()
    assert not alias.exists()


def test_harness_home_path_gemini(monkeypatch, tmp_path):
    """harness_home_path returns ~/.gemini for gemini."""
    from agent_toolkit_cli.commands._link_lib import harness_home_path

    monkeypatch.setenv("HOME", str(tmp_path))
    assert harness_home_path("gemini") == tmp_path / ".gemini"


def test_slot_filename_gemini_command_uses_toml_extension():
    from agent_toolkit_cli.commands._link_lib import _slot_filename

    assert _slot_filename("hello", "command", "gemini") == "hello.toml"


def test_translate_slot_layout_gemini_command_is_file():
    from agent_toolkit_cli.commands._link_lib import _translate_slot_layout

    assert _translate_slot_layout("gemini", "command") == "file"


def test_scope_cache_root_gemini_user(monkeypatch, tmp_path):
    from agent_toolkit_cli.commands._link_lib import _scope_cache_root

    monkeypatch.setenv("HOME", str(tmp_path))
    root = _scope_cache_root("gemini", "user", project_root=tmp_path / "ignored")
    assert root == tmp_path / ".gemini" / ".agent-toolkit-cache"


def test_scope_cache_root_gemini_project(tmp_path):
    from agent_toolkit_cli.commands._link_lib import _scope_cache_root

    proj = tmp_path / "p"
    proj.mkdir()
    root = _scope_cache_root("gemini", "project", project_root=proj)
    assert root == proj / ".gemini" / ".agent-toolkit-cache"


def test_slot_filename_gemini_agent_uses_md_extension():
    from agent_toolkit_cli.commands._link_lib import _slot_filename

    assert _slot_filename("demo", "agent", "gemini") == "demo.md"


def test_translate_slot_layout_gemini_agent_is_file():
    from agent_toolkit_cli.commands._link_lib import _translate_slot_layout

    assert _translate_slot_layout("gemini", "agent") == "file"


def _make_md_asset(tmp_path: Path, kind_dir: str, slug: str) -> Path:
    """Create a minimal asset file with `claude` declared in spec.harnesses."""
    root = tmp_path / "toolkit" / kind_dir / slug
    root.mkdir(parents=True)
    p = root / f"{slug}.md"
    p.write_text(
        "---\nspec:\n  harnesses: [claude]\n---\n# body\n",
        encoding="utf-8",
    )
    return p


def test_claude_command_slot_uses_md_suffix(tmp_path):
    asset = _make_md_asset(tmp_path, "commands", "demo-cmd")
    target_dir = tmp_path / ".claude" / "commands"
    target_dir.mkdir(parents=True)
    counters = LinkCounters()
    stdout = StringIO()

    maybe_link(
        harness="claude",
        kind="command",
        slug="demo-cmd",
        asset_path=asset,
        target_dir=target_dir,
        toolkit_root=tmp_path / "toolkit",
        dry_run=False,
        counters=counters,
        stdout=stdout,
        scope="project",
        project_root=tmp_path,
    )

    expected = target_dir / "demo-cmd.md"
    assert expected.is_symlink(), (
        f"expected {expected} to exist as a symlink; "
        f"dir contents: {sorted(p.name for p in target_dir.iterdir())}"
    )
    assert expected.resolve() == asset.resolve()
    assert not (target_dir / "demo-cmd").exists()


def test_claude_agent_slot_uses_md_suffix(tmp_path):
    asset = _make_md_asset(tmp_path, "agents", "demo-agent")
    target_dir = tmp_path / ".claude" / "agents"
    target_dir.mkdir(parents=True)
    counters = LinkCounters()
    stdout = StringIO()

    maybe_link(
        harness="claude",
        kind="agent",
        slug="demo-agent",
        asset_path=asset,
        target_dir=target_dir,
        toolkit_root=tmp_path / "toolkit",
        dry_run=False,
        counters=counters,
        stdout=stdout,
        scope="project",
        project_root=tmp_path,
    )

    expected = target_dir / "demo-agent.md"
    assert expected.is_symlink()
    assert expected.resolve() == asset.resolve()
    assert not (target_dir / "demo-agent").exists()


def test_claude_skill_slot_remains_bare_slug(tmp_path):
    """Regression: skills are directory-shaped and must NOT get a .md suffix."""
    root = tmp_path / "toolkit" / "skills" / "demo-skill"
    root.mkdir(parents=True)
    sk = root / "SKILL.md"
    sk.write_text(
        "---\nspec:\n  harnesses: [claude]\n---\n# body\n",
        encoding="utf-8",
    )
    target_dir = tmp_path / ".claude" / "skills"
    target_dir.mkdir(parents=True)
    counters = LinkCounters()
    stdout = StringIO()

    maybe_link(
        harness="claude",
        kind="skill",
        slug="demo-skill",
        asset_path=sk,
        target_dir=target_dir,
        toolkit_root=tmp_path / "toolkit",
        dry_run=False,
        counters=counters,
        stdout=stdout,
        scope="project",
        project_root=tmp_path,
    )

    expected = target_dir / "demo-skill"
    assert expected.is_symlink(), (
        f"expected bare-slug symlink at {expected}; "
        f"dir contents: {sorted(p.name for p in target_dir.iterdir())}"
    )
    assert expected.resolve() == root.resolve()
    assert not (target_dir / "demo-skill.md").exists()


def test_orphan_sweep_prunes_legacy_bare_slug_for_claude_command(tmp_path):
    """After upgrading from the pre-#82 version, an existing bare-slug
    `<slug>` symlink for a claude command should be pruned on the next
    `project_from_file` run (it's superseded by the `<slug>.md` symlink)."""
    toolkit = tmp_path / "toolkit"
    (toolkit / "commands" / "legacy-cmd").mkdir(parents=True)
    asset = toolkit / "commands" / "legacy-cmd" / "legacy-cmd.md"
    asset.write_text(
        "---\nspec:\n  harnesses: [claude]\n---\n# legacy\n",
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    allowlist = project / ".agent-toolkit.yaml"
    allowlist.write_text(
        "skills: []\nagents: []\ncommands:\n- legacy-cmd\n"
        "hooks: []\nplugins: []\nmcps: []\npi_extensions: []\n",
        encoding="utf-8",
    )
    target_dir = project / ".claude" / "commands"
    target_dir.mkdir(parents=True)
    legacy = target_dir / "legacy-cmd"
    legacy.symlink_to(asset)

    from agent_toolkit_cli.commands._link_lib import project_from_file

    counters = LinkCounters()
    stdout = StringIO()
    project_from_file(
        scope="project",
        harness="claude",
        toolkit_root=toolkit,
        project_root=project,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=stdout,
    )

    assert (target_dir / "legacy-cmd.md").is_symlink()
    assert not (target_dir / "legacy-cmd").exists(), (
        "legacy bare-slug symlink should have been pruned on upgrade; "
        f"dir contents: {sorted(p.name for p in target_dir.iterdir())}"
    )


def test_doctor_symlinks_no_false_stale_for_claude_command_md(tmp_path, monkeypatch):
    """doctor symlink-integrity check should NOT report a stale-link warning
    for a properly-linked claude command (which now lives at `<slug>.md`)."""
    toolkit = tmp_path / "toolkit"
    (toolkit / "commands" / "live-cmd").mkdir(parents=True)
    asset = toolkit / "commands" / "live-cmd" / "live-cmd.md"
    asset.write_text(
        "---\nspec:\n  harnesses: [claude]\n---\n# live\n",
        encoding="utf-8",
    )

    fake_home = tmp_path / "home"
    user_cmds = fake_home / ".claude" / "commands"
    user_cmds.mkdir(parents=True)
    (user_cmds / "live-cmd.md").symlink_to(asset)

    monkeypatch.setenv("HOME", str(fake_home))

    from agent_toolkit_cli.doctor.symlinks import run as check_symlink_integrity

    result = check_symlink_integrity(toolkit, harness="claude")
    bad = [
        f for f in (result.findings or [])
        if "stale link" in f or "dangling" in f or "not in spec.harnesses" in f
    ]
    assert not bad, f"expected no stale-link findings, got: {bad}"
