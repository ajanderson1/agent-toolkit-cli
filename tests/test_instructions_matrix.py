"""Parity test for the all-harness instruction-file (instructions kind) support table.

The table lives in docs/agent-toolkit/harness-matrix.md under the heading
"## Instruction-file (`instructions` kind) support — all harnesses". Every
harness in the catalog (agent_toolkit_cli.skill_agents, excluding the synthetic
`universal`, `standard-skill`, and `standard-agent` entries) must appear exactly
once with a recognised verdict.

Symlink-verdict rows (the Phase B work surface) must additionally carry a
non-empty default-file cell, paths cell, and citation.

This is the Phase A gate: the table is the contract Phase B implements against.
Counterpart to `tests/test_subagent_matrix.py`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent_toolkit_cli import skill_agents

_REPO_ROOT = Path(__file__).parent.parent
_DOC_PATH = _REPO_ROOT / "docs" / "agent-toolkit" / "harness-matrix.md"

# The 5 verdict keywords the instructions kind uses. Smaller vocabulary than
# the subagent kind — pointers are the only action.
_VERDICTS = (
    "native",
    "symlink",
    "unsupported (gap)",
    "unsupported (by design)",
    "unknown",
)

# Section heading that contains the 54-row table.
_SECTION_HEADING = "## Instruction-file (`instructions` kind) support — all harnesses"

# Row shape: | `<harness>` | <verdict> | <default> | <paths> | <native?> | <mechanism> | <citation> |
_ROW_RE = re.compile(
    r"^\|\s*`(?P<harness>[a-z][a-z0-9-]*)`\s*\|"
    r"(?P<verdict>[^|]+)\|"
    r"(?P<default>[^|]*)\|"
    r"(?P<paths>[^|]*)\|"
    r"(?P<native>[^|]*)\|"
    r"(?P<mechanism>[^|]*)\|"
    r"(?P<citation>[^|]*)\|"
)


def _catalog_harnesses() -> set[str]:
    """All catalog harness names except synthetic pseudo-entries.

    Mirrors `test_subagent_matrix._catalog_harnesses` — both tables index the
    same catalog and exclude the same synthetics. `standard-agent` is the
    agent-kind synthetic added in PR2 of #252; it resolves to a convergence
    path and is not an instruction-file harness, so it is excluded here too.
    """
    return set(skill_agents.AGENTS) - {"standard", "standard-skill", "standard-agent"}


def _parse_section() -> dict[str, dict[str, str]]:
    """Return {harness: {verdict, default, paths, native, mechanism, citation}}."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    if _SECTION_HEADING not in text:
        return {}
    section = text.split(_SECTION_HEADING, 1)[1]
    # Stop at the next H2 so we only parse this section's rows.
    section = re.split(r"^## ", section, maxsplit=1, flags=re.MULTILINE)[0]
    rows: dict[str, dict[str, str]] = {}
    for line in section.splitlines():
        m = _ROW_RE.match(line.strip())
        if m is None:
            continue
        rows[m.group("harness")] = {
            "verdict": m.group("verdict").strip(),
            "default": m.group("default").strip(),
            "paths": m.group("paths").strip(),
            "native": m.group("native").strip(),
            "mechanism": m.group("mechanism").strip(),
            "citation": m.group("citation").strip(),
        }
    return rows


@pytest.fixture(scope="module")
def rows() -> dict[str, dict[str, str]]:
    assert _DOC_PATH.exists(), f"{_DOC_PATH} not found"
    parsed = _parse_section()
    assert parsed, (
        f"No rows parsed under '{_SECTION_HEADING}'. The instructions-kind "
        "Phase A table must be assembled before this test can pass."
    )
    return parsed


def test_all_catalog_harnesses_present(rows):
    """Every catalog harness must appear exactly once in the instructions table."""
    catalog = _catalog_harnesses()
    table = set(rows)
    missing = catalog - table
    extra = table - catalog
    assert not missing, f"Harnesses missing from instructions table: {sorted(missing)}"
    assert not extra, f"Unknown harnesses in instructions table: {sorted(extra)}"


def test_every_verdict_recognised(rows):
    """Each row's verdict cell must start with a known instructions-kind verdict."""
    bad = {
        h: r["verdict"]
        for h, r in rows.items()
        if not r["verdict"].lower().startswith(_VERDICTS)
    }
    assert not bad, f"Rows with unrecognised verdict: {bad}"


def test_symlink_rows_have_default_paths_citation(rows):
    """A 'symlink' verdict is the only action verdict — it must carry the
    pointer fields the Phase B adapter needs: default file name, project/global
    paths, and a citation backing the loader behaviour."""
    incomplete = {
        h: r
        for h, r in rows.items()
        if r["verdict"].lower().startswith("symlink")
        and not (r["default"] and r["paths"] and r["citation"])
    }
    assert not incomplete, (
        f"Symlink-verdict rows missing default/paths/citation: {sorted(incomplete)}"
    )


def test_symlink_rows_declare_symlink_mechanism(rows):
    """Symlink-verdict rows must carry mechanism='symlink' (the one action
    keyword for this kind). Non-symlink rows must leave the mechanism cell
    blank — there is no `translate`/`config_file` for instructions."""
    bad_symlink = {
        h: r["mechanism"]
        for h, r in rows.items()
        if r["verdict"].lower().startswith("symlink") and r["mechanism"] != "symlink"
    }
    bad_other = {
        h: r["mechanism"]
        for h, r in rows.items()
        if not r["verdict"].lower().startswith("symlink") and r["mechanism"]
    }
    assert not bad_symlink, (
        f"Symlink-verdict rows with wrong/missing mechanism: {bad_symlink}"
    )
    assert not bad_other, (
        f"Non-symlink rows with a mechanism (should be blank): {bad_other}"
    )


def test_native_versus_agents_md_column_agree(rows):
    """The 'reads AGENTS.md natively?' column is the bucket discriminator and
    must match the verdict: native ↔ yes, everything else ↔ no."""
    inconsistent = {}
    for h, r in rows.items():
        is_native = r["verdict"].lower().startswith("native")
        reads_natively = r["native"].lower().startswith("yes")
        if is_native != reads_natively:
            inconsistent[h] = (r["verdict"], r["native"])
    assert not inconsistent, (
        f"Verdict ↔ 'reads AGENTS.md natively?' disagreement: {inconsistent}"
    )
