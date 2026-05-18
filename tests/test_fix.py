from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _seed_repo(repo: Path) -> None:
    (repo / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (repo / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (repo / "skills" / "alpha").mkdir(parents=True)
    (repo / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: Alpha.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
    )
    (repo / "AGENTS.md").write_text(
        "# Agent Conventions\n"
        "\n"
        "<!-- BEGIN_AGENT_TOOLKIT:component-table -->\n"
        "OLD\n"
        "<!-- END_AGENT_TOOLKIT:component-table -->\n"
        "\n"
        "<!-- BEGIN_AGENT_TOOLKIT:submodule-table -->\n"
        "OLD\n"
        "<!-- END_AGENT_TOOLKIT:submodule-table -->\n"
    )


def test_fix_regenerates_component_table(tmp_path):
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["fix", "--toolkit-repo", str(tmp_path)])
    assert result.exit_code == 0, result.output

    text = (tmp_path / "AGENTS.md").read_text()
    assert "OLD" not in text
    assert "Skills" in text  # component table populated
    assert "BEGIN_AGENT_TOOLKIT:component-table" in text


def test_fix_only_filters_generators(tmp_path):
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["fix", "--toolkit-repo", str(tmp_path), "--only", "component-table"],
    )
    assert result.exit_code == 0
    text = (tmp_path / "AGENTS.md").read_text()
    # component-table updated; submodule-table still has OLD
    assert "Skills" in text
    submodule_section = text.split("BEGIN_AGENT_TOOLKIT:submodule-table")[1]
    assert "OLD" in submodule_section


def test_fix_to_stdout_does_not_modify_file(tmp_path):
    _seed_repo(tmp_path)
    original = (tmp_path / "AGENTS.md").read_text()
    runner = CliRunner()
    result = runner.invoke(main, ["fix", "--toolkit-repo", str(tmp_path), "--to-stdout"])
    assert result.exit_code == 0
    assert (tmp_path / "AGENTS.md").read_text() == original
    assert "BEGIN_AGENT_TOOLKIT:component-table" in result.output


def test_fix_emits_header_and_summary_on_stderr(tmp_path):
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["fix", "--toolkit-repo", str(tmp_path)])
    assert result.exit_code == 0
    # Header and summary are emitted to stderr via _ui module
    # CliRunner's result.output includes both stdout and stderr
    assert "Regenerating" in result.output
    assert "Updated AGENTS.md" in result.output


def test_fix_to_stdout_summary_says_file_unchanged(tmp_path):
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["fix", "--toolkit-repo", str(tmp_path), "--to-stdout"])
    assert result.exit_code == 0
    # Summary mentions file unchanged
    assert "file unchanged" in result.output.lower() or "stdout" in result.output.lower()
    # Rendered AGENTS.md content is in output
    assert "BEGIN_AGENT_TOOLKIT:component-table" in result.output


def _seed_mcp_in_repo(repo: Path) -> None:
    """Add a context7 MCP to an existing repo (assumes _seed_repo already ran)."""
    mcp_dir = repo / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )


def test_fix_reconciles_mcp_drift(tmp_path, monkeypatch):
    """fix reconciles drifted codex MCP entries to canonical form."""
    from click.testing import CliRunner

    from agent_toolkit_cli.cli import main
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    _seed_repo(tmp_path)
    _seed_mcp_in_repo(tmp_path)

    # Install via adapter then drift.
    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    target = home / ".codex" / "config.toml"
    target.write_bytes(act.contents)
    text = target.read_text().replace(
        '"@upstash/context7-mcp"', '"@upstash/context7-mcp", "--debug"'
    )
    target.write_text(text)
    assert a.entry_drift("user", tmp_path, entry) is True

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["fix", "--toolkit-repo", str(tmp_path), "--harness", "codex", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    # After fix, no drift.
    assert a.entry_drift("user", tmp_path, entry) is False


def test_fix_skips_unimplemented_harness(tmp_path, monkeypatch):
    """fix --harness pi prints skip and does not error.

    Pi remains UnimplementedAdapter (Pi has no MCP support by design).
    """
    from click.testing import CliRunner

    from agent_toolkit_cli.cli import main

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    _seed_repo(tmp_path)
    _seed_mcp_in_repo(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["fix", "--toolkit-repo", str(tmp_path),
         "--harness", "pi", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    assert "no MCP adapter for harness pi yet" in result.output


def test_fix_mcps_only_skips_agents_md(tmp_path, monkeypatch):
    """--mcps-only skips AGENTS.md region regen; only does MCP reconcile."""
    from click.testing import CliRunner

    from agent_toolkit_cli.cli import main
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    _seed_repo(tmp_path)
    _seed_mcp_in_repo(tmp_path)

    # Install + drift.
    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    target = home / ".codex" / "config.toml"
    target.write_bytes(act.contents)
    text = target.read_text().replace(
        '"@upstash/context7-mcp"', '"@upstash/context7-mcp", "--debug"'
    )
    target.write_text(text)

    # Capture AGENTS.md content before fix.
    agents_before = (tmp_path / "AGENTS.md").read_text()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["fix", "--toolkit-repo", str(tmp_path),
         "--harness", "codex", "--scope", "user", "--mcps-only"],
    )
    assert result.exit_code == 0, result.output

    # AGENTS.md unchanged (still has the seed's "OLD" placeholder).
    assert (tmp_path / "AGENTS.md").read_text() == agents_before
    # MCP reconciled: no drift.
    assert a.entry_drift("user", tmp_path, entry) is False


def test_fix_mcp_no_op_when_no_drift(tmp_path, monkeypatch):
    """fix is a no-op (no writes) when MCPs are already aligned."""
    from click.testing import CliRunner

    from agent_toolkit_cli.cli import main
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    _seed_repo(tmp_path)
    _seed_mcp_in_repo(tmp_path)

    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    target = home / ".codex" / "config.toml"
    target.write_bytes(act.contents)

    mtime_before = target.stat().st_mtime_ns

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["fix", "--toolkit-repo", str(tmp_path),
         "--harness", "codex", "--scope", "user", "--mcps-only"],
    )
    assert result.exit_code == 0, result.output
    # No write happened (mtime preserved).
    assert target.stat().st_mtime_ns == mtime_before
