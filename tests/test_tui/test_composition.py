"""Column composition for the Standard / Non-standard split (#351).

The TUI renders the standard column plus the non-covered MAIN_HARNESSES only;
the long tail is CLI-only (post-demo AJ decision). The coverage guard below is
the load-bearing invariant: every main harness must be covered — standard or
own column — on every asset type it supports.
"""
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.composition import (
    MAIN_HARNESSES,
    _MCP_HARNESSES,
    instructions_nonstandard_main,
    mcp_nonstandard_main,
    skills_nonstandard_main,
)


def test_main_harnesses_members():
    assert MAIN_HARNESSES == (
        "claude-code", "gemini-cli", "codex", "opencode", "pi", "cursor",
        "hermes-agent", "paperclip",
    )


def test_skills_nonstandard_main_today():
    # gemini-cli / codex / opencode / cursor read .agents/skills → standard;
    # paperclip is a non-standard, company-scoped skills column (issue #474).
    assert skills_nonstandard_main() == (
        "claude-code", "pi", "hermes-agent", "paperclip",
    )


def test_paperclip_is_not_actionable_in_other_asset_compositions():
    from agent_toolkit_cli.command_adapters import SUPPORTED_HARNESSES as _CMD
    from agent_toolkit_tui.composition import agents_nonstandard_main

    assert "paperclip" not in instructions_nonstandard_main()
    assert all(
        "paperclip" not in agents_nonstandard_main(scope)
        for scope in ("global", "project")
    )
    assert "paperclip" not in _MCP_HARNESSES
    assert "paperclip" not in _CMD


def test_instructions_nonstandard_main_today():
    # codex / opencode / pi / cursor / hermes-agent read AGENTS.md natively → standard.
    assert instructions_nonstandard_main() == ("claude-code", "gemini-cli")


def test_skills_coverage_guard():
    """Every main harness is standard-covered or has its own skills column."""
    standard = {n for n, c in AGENTS.items() if c.is_standard}
    rendered = set(skills_nonstandard_main())
    for h in MAIN_HARNESSES:
        assert h in standard or h in rendered, (
            f"{h} is neither standard-covered nor a rendered skills column"
        )


def test_instructions_coverage_guard():
    """Every main harness that supports the instructions asset type is covered:
    native verdict (standard column) or a rendered pointer column."""
    from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows

    verdicts = {r["harness"]: r["verdict"] for r in instructions_matrix_rows()}
    assert verdicts["hermes-agent"] == "native"
    rendered = set(instructions_nonstandard_main())
    for h in MAIN_HARNESSES:
        verdict = verdicts.get(h, "")
        if verdict.startswith("unsupported") or verdict.startswith("unknown"):
            continue  # the harness can't consume the asset type at all
        assert verdict == "native" or h in rendered, (
            f"{h} (verdict {verdict!r}) is neither native (standard) nor a "
            f"rendered instructions column"
        )


def test_rendered_columns_disjoint_from_standard():
    standard = {n for n, c in AGENTS.items() if c.is_standard and c.show_in_standard_list}
    assert set(skills_nonstandard_main()).isdisjoint(standard)


def test_agents_nonstandard_main_today():
    from agent_toolkit_tui.composition import agents_nonstandard_main

    # claude-code AND cursor are standard-covered (cursor per the 2026-06-10
    # re-verification); codex and hermes-agent are unsupported-by-design;
    # gemini-cli/opencode/pi keep their own columns. MAIN_HARNESSES declaration
    # order, filtered — same convention as the skills/instructions helpers.
    assert AGENTS["hermes-agent"].subagent_mechanism == "none"
    assert agents_nonstandard_main("global") == ("gemini-cli", "opencode", "pi")
    assert agents_nonstandard_main("project") == ("gemini-cli", "opencode", "pi")
    assert all(
        "hermes-agent" not in agents_nonstandard_main(scope)
        for scope in ("global", "project")
    )


def test_agents_coverage_guard():
    """Every main harness that supports the agent asset type is covered: in
    the standard readers set or a rendered column."""
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
    from agent_toolkit_tui.composition import agents_nonstandard_main

    for scope in ("global", "project"):
        covered = agents_standard_covered(scope)
        rendered = set(agents_nonstandard_main(scope))
        for h in MAIN_HARNESSES:
            if AGENTS[h].subagent_mechanism == "none":
                continue  # e.g. codex: unsupported by design — exempt
            assert h in covered or h in rendered, (
                f"{h} is neither standard-covered nor rendered on the agents tab ({scope})"
            )


def test_mcp_harnesses_members():
    # The four real MCP harnesses (commands/mcp/_common.py _HARNESSES), in
    # canonical render order. NOT MAIN_HARNESSES (no gemini-cli / cursor).
    assert _MCP_HARNESSES == ("claude-code", "codex", "opencode", "pi")


def test_mcp_nonstandard_main_project():
    # claude-code + pi fold into the project standard (.mcp.json) → only the
    # two non-covered harnesses get their own column.
    assert mcp_nonstandard_main("project") == ("codex", "opencode")


def test_mcp_nonstandard_main_global():
    # Global has no standard (STANDARD_MCP_READERS lacks a 'global' key);
    # mcp_standard_covered('global') raises KeyError → empty covered set →
    # all four harnesses render their own column.
    assert mcp_nonstandard_main("global") == (
        "claude-code", "codex", "opencode", "pi",
    )


def test_mcp_coverage_guard():
    """Every MCP harness is standard-covered (project) or has its own column."""
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered
    for scope in ("global", "project"):
        try:
            covered = set(mcp_standard_covered(scope))
        except KeyError:
            covered = set()
        rendered = set(mcp_nonstandard_main(scope))
        for h in _MCP_HARNESSES:
            assert h in covered or h in rendered, (
                f"{h} is neither standard-covered nor a rendered MCP column at {scope}"
            )
