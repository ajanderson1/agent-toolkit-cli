import pytest

from agent_toolkit.commands._link_lib import (
    ALL_HARNESSES,
    MALFORMED,
    LinkCounters,
    format_summary,
    iter_plan_lines,
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
    from agent_toolkit.commands._link_lib import harness_home_path

    monkeypatch.setenv("HOME", str(tmp_path))
    assert harness_home_path("claude") == tmp_path / ".claude"
    assert harness_home_path("pi") == tmp_path / ".pi"


def test_harness_home_path_explicit_home_overrides_env(tmp_path):
    from pathlib import Path as _P
    from agent_toolkit.commands._link_lib import harness_home_path

    other = tmp_path / "other-home"
    assert harness_home_path("codex", home=other) == other / ".codex"
    assert harness_home_path("opencode", home=_P("/tmp/x")) == _P("/tmp/x/.opencode")


def test_project_from_file_codex_mcp_dispatches_to_adapter(tmp_path, monkeypatch):
    """Codex + allow-listed MCP → adapter writes target file."""
    import io

    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

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


def test_project_from_file_claude_mcp_skips_loudly(tmp_path, monkeypatch):
    """Claude + allow-listed MCP → loud skip, exit clean, no file written."""
    import io

    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".claude").mkdir(parents=True)

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
        "    - claude\n"
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
        scope="user", harness="claude", toolkit_root=toolkit_root,
        project_root=project_root, allowlist_path=allowlist,
        dry_run=False, counters=counters, stdout=buf,
    )

    out = buf.getvalue()
    assert "no MCP adapter for harness claude yet — skipping" in out
    assert counters.created == 0
