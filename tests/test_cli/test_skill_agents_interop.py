"""Interop test: assert every agent in vendored vercel-labs/skills agents.ts
appears in our AGENTS dict.

If skills.sh adds an agent and a new agents.ts is vendored to
tests/fixtures/, this test fails until the Python catalog is synced.
"""
from __future__ import annotations

import re
from pathlib import Path

from agent_toolkit_cli.skill_agents import AGENTS


def _extract_agent_names_from_ts(ts_source: str) -> set[str]:
    """Parse agent names from the TS object literal.

    Looks for lines like:
        'aider-desk': {
        amp: {
        'claude-code': {

    Skips lines inside detect_installed lambdas etc. by anchoring to
    the top-level 'agents' map.
    """
    # Find the start of the agents declaration.
    match = re.search(
        r"agents:\s*Record<AgentType,\s*AgentConfig>\s*=\s*\{",
        ts_source,
    )
    assert match, "could not find agents map in TS source"
    # Names are property keys at indentation level 2: 2 spaces then ident or 'quoted-name':
    name_pat = re.compile(
        r"^  (?:'([a-z0-9-]+)':|([a-z0-9-]+):)\s*\{",
        re.MULTILINE,
    )
    body = ts_source[match.end():]
    names: set[str] = set()
    for m in name_pat.finditer(body):
        names.add(m.group(1) or m.group(2))
    return names


def test_catalog_matches_vendored_skills_sh_source():
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "vercel-labs-skills-agents.ts"
    )
    if not fixture.exists():
        # Fixture not yet vendored; skip.
        import pytest

        pytest.skip("vendored agents.ts not present at " + str(fixture))
    ts_names = _extract_agent_names_from_ts(fixture.read_text())
    py_names = set(AGENTS.keys())
    missing_in_py = ts_names - py_names
    extra_in_py = py_names - ts_names
    assert not missing_in_py, (
        f"agents in vercel-labs/skills but missing from Python catalog: "
        f"{sorted(missing_in_py)}"
    )
    # extra_in_py is allowed (we might have helpers); but warn loudly:
    if extra_in_py:
        print(
            f"WARN: agents in Python catalog not in skills.sh: {sorted(extra_in_py)}"
        )
