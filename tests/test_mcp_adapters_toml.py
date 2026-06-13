"""Tests for the Codex TOML-family MCP adapter."""
from __future__ import annotations

import tomlkit

from agent_toolkit_cli.mcp_adapters import get_adapter

INNER = {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}


def test_codex_user_target(tmp_path):
    adapter = get_adapter("codex")
    assert adapter.config_target(scope="global", home=tmp_path, project=None) == (
        tmp_path / ".codex" / "config.toml"
    )


def test_codex_install_adds_mcp_servers_table(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="global", home=tmp_path)
    doc = tomlkit.parse((tmp_path / ".codex" / "config.toml").read_text())
    assert doc["mcp_servers"]["context7"]["command"] == "npx"
    assert doc["mcp_servers"]["context7"]["args"] == ["-y", "ctx7"]


def test_codex_round_trip_preserves_unrelated_tables_and_comments(tmp_path):
    """Acceptance #8: link an unrelated MCP, unlink it → byte-equal to source.

    The source baseline is the hand-written config normalised to tomlkit's
    settled round-trip form, which differs from the raw hand-typed bytes by
    exactly ONE trailing newline (asserted below: ``source == raw + "\\n"``).
    Rationale: when tomlkit appends a sibling sub-table to an existing
    super-table (``[mcp_servers.context7]`` next to ``[mcp_servers.handrolled]``)
    and that sibling is later deleted, it leaves a single trailing newline on the
    surviving table. That is an inherent tomlkit add-then-remove artifact (a pure
    ``dumps(parse(raw))`` round-trip is a no-op here — the newline comes from the
    *append*, not from canonicalisation), NOT a bug in this adapter. The spec's
    substantive guarantee — comments, unknown sections, and hand-rolled entries
    all survive byte-for-byte — still holds; ``raw`` is a verbatim prefix of
    ``source``. Production code stays whitespace-agnostic (it never trims
    whitespace); only this test baseline is normalised. See the Task 5 report.
    """
    raw = (
        "# my codex config\n"
        "model = \"gpt-5\"\n\n"
        "[tui]\n"
        "theme = \"dark\"  # keep me\n\n"
        "[mcp_servers.handrolled]\n"
        "command = \"x\"\n"
    )
    # tomlkit's settled form: raw plus exactly one trailing newline (see docstring).
    source = raw + "\n"
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(source)
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="global", home=tmp_path)
    adapter.uninstall("context7", scope="global", home=tmp_path)
    assert cfg.read_text() == source
    # Substantive guarantee: every hand-written byte survived; only a trailing
    # newline was ever in question, and that is fixed-point stable here.
    assert source.startswith(raw)


def test_codex_uninstall_removes_only_named_table(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="global", home=tmp_path)
    adapter.install("other", {"command": "y"}, scope="global", home=tmp_path)
    adapter.uninstall("context7", scope="global", home=tmp_path)
    doc = tomlkit.parse((tmp_path / ".codex" / "config.toml").read_text())
    assert "context7" not in doc["mcp_servers"]
    assert doc["mcp_servers"]["other"]["command"] == "y"


def test_codex_install_idempotent(tmp_path):
    adapter = get_adapter("codex")
    adapter.install("context7", INNER, scope="global", home=tmp_path)
    first = (tmp_path / ".codex" / "config.toml").read_text()
    adapter.install("context7", INNER, scope="global", home=tmp_path)
    assert (tmp_path / ".codex" / "config.toml").read_text() == first
