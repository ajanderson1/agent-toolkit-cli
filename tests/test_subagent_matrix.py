"""Parity test for the all-harness subagent (agent kind) support table.

The table lives in docs/agent-toolkit/harness-matrix.md under the heading
"## Subagent (agent kind) support — all harnesses". Every harness in the
catalog (agent_toolkit_cli.skill_agents, excluding the synthetic `universal`
entry) must appear exactly once with a recognised verdict. Supported rows
must additionally carry a mechanism keyword, a target path, and a citation.

This is the Phase A gate: the table is the contract Phase B implements against.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent_toolkit_cli import skill_agents

_REPO_ROOT = Path(__file__).parent.parent
_DOC_PATH = _REPO_ROOT / "docs" / "agent-toolkit" / "harness-matrix.md"

# Verdict keywords a cell may start with. "unknown" is new in v3.0.0 Phase A
# for time-boxed-no-evidence harnesses; the rest reuse the matrix vocabulary.
_VERDICTS = (
    "symlink",
    "translate",
    "config_file+folder",
    "config_file",
    "dual-symlink",
    "unsupported (gap)",
    "unsupported (by design)",
    "unknown",
)

# Section heading that contains the 54-row table.
_SECTION_HEADING = "## Subagent (agent kind) support — all harnesses"

# Row shape: | `<harness>` | <verdict cell> | <mechanism> | <path> | <format> | <citation> |
_ROW_RE = re.compile(
    r"^\|\s*`(?P<harness>[a-z][a-z0-9-]*)`\s*\|"
    r"(?P<verdict>[^|]+)\|"
    r"(?P<mechanism>[^|]*)\|"
    r"(?P<path>[^|]*)\|"
    r"(?P<fmt>[^|]*)\|"
    r"(?P<citation>[^|]*)\|"
)


def _catalog_harnesses() -> set[str]:
    """All catalog harness names except synthetic pseudo-entries.

    `skill_agents.AGENTS` is a dict[str, AgentConfig] keyed by harness name.
    `universal`, `standard-skill` (added in PR1 of #252), and `standard-agent`
    (added in PR2 of #252) are synthetic — they resolve to convergence paths
    and are not real harnesses, so they're excluded from the harness-support matrix.
    """
    return set(skill_agents.AGENTS) - {"standard", "standard-skill", "standard-agent"}


def _parse_section() -> dict[str, dict[str, str]]:
    """Return {harness: {verdict, mechanism, path, fmt, citation}} from the table."""
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
            "mechanism": m.group("mechanism").strip(),
            "path": m.group("path").strip(),
            "fmt": m.group("fmt").strip(),
            "citation": m.group("citation").strip(),
        }
    return rows


@pytest.fixture(scope="module")
def rows() -> dict[str, dict[str, str]]:
    assert _DOC_PATH.exists(), f"{_DOC_PATH} not found"
    parsed = _parse_section()
    assert parsed, (
        f"No rows parsed under '{_SECTION_HEADING}'. Assemble the table "
        "(Task 4) before this test can pass."
    )
    return parsed


def test_all_catalog_harnesses_present(rows):
    """Every catalog harness must appear exactly once in the table."""
    catalog = _catalog_harnesses()
    table = set(rows)
    missing = catalog - table
    extra = table - catalog
    assert not missing, f"Harnesses missing from subagent table: {sorted(missing)}"
    assert not extra, f"Unknown harnesses in subagent table: {sorted(extra)}"


def test_every_verdict_recognised(rows):
    """Each row's verdict cell must start with a known verdict keyword."""
    bad = {
        h: r["verdict"]
        for h, r in rows.items()
        if not r["verdict"].lower().startswith(_VERDICTS)
    }
    assert not bad, f"Rows with unrecognised verdict: {bad}"


def test_supported_rows_have_mechanism_path_citation(rows):
    """A 'supported' verdict (symlink/translate/config_file/dual-symlink) must
    carry a non-empty mechanism, path, and citation."""
    supported_prefixes = ("symlink", "translate", "config_file", "dual-symlink")
    incomplete = {
        h: r
        for h, r in rows.items()
        if r["verdict"].lower().startswith(supported_prefixes)
        and not (r["mechanism"] and r["path"] and r["citation"])
    }
    assert not incomplete, (
        f"Supported rows missing mechanism/path/citation: {sorted(incomplete)}"
    )


# Verdict prefix → expected AgentConfig.subagent_mechanism value.
# config_file+folder rows use the Python identifier config_file_folder.
# dual-symlink rows were reclassified to the symlink mechanism per spec
# addendum Correction A (the ~/.agents/ user-scope slot is a skills path).
_VERDICT_PREFIX_TO_MECHANISM: dict[str, str] = {
    "symlink": "symlink",
    "translate": "translate",
    "config_file+folder": "config_file_folder",
    "config_file": "config_file_folder",
    "dual-symlink": "symlink",
}


# Cells the matrix classifies as supported but that remain intentionally
# disabled (subagent_mechanism='none') pending an explicit AJ decision on
# shared-config mutation (PR5a). Both cells write to a shared registry file
# owned by a third-party tool; aider-desk + dexto were enabled in PR4 because
# they write only self-owned per-slug files. Re-enabling codex or firebender
# requires updating both this set AND the literal in skill_agents.py.
# Both disabled cells MUST carry a non-empty disabled_reason (see
# test_reasoned_disabled_cells_have_reason below).
PR2_DISABLED_DESPITE_MATRIX_SUPPORT = frozenset({
    "codex", "firebender",
})


def test_supported_rows_have_matching_adapter(rows):
    """Every harness-matrix row with a supported-mechanism verdict must
    have a corresponding agent_adapters.get_adapter() implementation,
    UNLESS the cell is in PR2_DISABLED_DESPITE_MATRIX_SUPPORT.

    Acceptance criterion #5 (spec): every supported matrix row has a
    subagent_mechanism value on its AgentConfig matching the row's verdict
    prefix, AND get_adapter(harness) returns an installable adapter.
    """
    from agent_toolkit_cli.agent_adapters import (
        UnsupportedMechanismError,
        get_adapter,
    )

    supported_prefixes = tuple(_VERDICT_PREFIX_TO_MECHANISM)
    failures: list[str] = []

    for harness, row in rows.items():
        verdict = row["verdict"].lower()
        if not verdict.startswith(supported_prefixes):
            continue  # unsupported (gap/by design) or unknown — skip

        # Determine which prefix matched.
        matched_prefix = next(
            p for p in sorted(_VERDICT_PREFIX_TO_MECHANISM, key=len, reverse=True)
            if verdict.startswith(p)
        )
        expected_mech = _VERDICT_PREFIX_TO_MECHANISM[matched_prefix]

        if harness not in skill_agents.AGENTS:
            failures.append(
                f"{harness}: matrix-listed as supported but missing from AGENTS catalog"
            )
            continue

        actual_mech = skill_agents.AGENTS[harness].subagent_mechanism

        # PR2-disabled cells: matrix says supported, catalog says 'none'.
        # The disable is documented + tested elsewhere (the e2e suite has a
        # parametrized test_pr2_disabled_cells_skip_cleanly). Skip the
        # adapter-importability check here.
        if harness in PR2_DISABLED_DESPITE_MATRIX_SUPPORT:
            if actual_mech != "none":
                failures.append(
                    f"{harness}: in PR2_DISABLED_DESPITE_MATRIX_SUPPORT but "
                    f"subagent_mechanism='{actual_mech}' (must be 'none'). "
                    f"If you re-enabled it, also remove from the set."
                )
            continue

        if actual_mech != expected_mech:
            failures.append(
                f"{harness}: matrix verdict prefix '{matched_prefix}' expects "
                f"subagent_mechanism='{expected_mech}', got '{actual_mech}'"
            )
            continue

        # Adapter must be importable and have install/uninstall.
        try:
            adapter = get_adapter(harness)
        except UnsupportedMechanismError as exc:
            failures.append(f"{harness}: get_adapter raised UnsupportedMechanismError: {exc}")
            continue

        missing = [m for m in ("install", "uninstall") if not hasattr(adapter, m)]
        if missing:
            failures.append(
                f"{harness}: adapter missing methods: {missing}"
            )

    assert not failures, "Matrix parity failures:\n" + "\n".join(failures)


def test_every_catalog_supported_mechanism_appears_in_matrix(rows):
    """Inverse of test_supported_rows_have_matching_adapter.

    If an AgentConfig has subagent_mechanism != 'none' but the harness
    isn't a supported row in harness-matrix.md, the catalog and matrix
    are out of sync. Catches the case where someone wires an adapter for
    a harness without first documenting/verifying its support in the matrix.
    """
    supported_prefixes = tuple(_VERDICT_PREFIX_TO_MECHANISM)
    catalog_with_real_mechanism = {
        name for name, cfg in skill_agents.AGENTS.items()
        if cfg.subagent_mechanism != "none"
        and name not in {"standard", "standard-skill", "standard-agent"}
    }
    matrix_supported = {
        h for h, row in rows.items()
        if row["verdict"].lower().startswith(supported_prefixes)
    }
    orphans = catalog_with_real_mechanism - matrix_supported
    assert not orphans, (
        "Catalog has subagent_mechanism set on harnesses NOT listed as "
        f"supported in harness-matrix.md: {sorted(orphans)}.\n"
        "Either add the row to the matrix, or set subagent_mechanism='none'."
    )


# ── PR4 additions: aider-desk + dexto supported; codex + firebender reasoned ─


def test_aider_desk_and_dexto_are_supported_via_config_file_folder():
    """PR4: aider-desk + dexto must have subagent_mechanism='config_file_folder'.

    Locks the PR4 enable. If someone reverts either cell to 'none', this test
    fails loudly so the PR4 install-machinery tests (test_aider_desk_dexto_cells)
    cannot be silently broken by a catalog revert.
    """
    from agent_toolkit_cli.skill_agents import AGENTS

    for harness in ("aider-desk", "dexto"):
        cfg = AGENTS[harness]
        assert cfg.subagent_mechanism == "config_file_folder", (
            f"{harness}: expected subagent_mechanism='config_file_folder' "
            f"(enabled in PR4), got {cfg.subagent_mechanism!r}. "
            "If you reverted the catalog, re-apply the PR4 change."
        )


def test_reasoned_disabled_cells_have_reason():
    """codex + firebender must carry a non-empty disabled_reason string.

    The reason is surfaced in doctor/capability output so users understand
    WHY the cell is not installable rather than seeing a silent omission.
    A cell with subagent_mechanism='none' and no reason is treated as
    unclassified (like `amp`), NOT intentionally-disabled — the distinction
    matters for UX and for future PR5a planning.
    """
    from agent_toolkit_cli.skill_agents import AGENTS

    for harness in ("codex", "firebender"):
        cfg = AGENTS[harness]
        assert cfg.subagent_mechanism == "none", (
            f"{harness}: expected to remain disabled (mechanism='none') — "
            "do not enable without an explicit AJ decision (PR5a)."
        )
        assert cfg.disabled_reason, (
            f"{harness}: has subagent_mechanism='none' (intentionally disabled) "
            "but disabled_reason is empty. Add a human-readable reason string "
            "to AgentConfig so doctor/capability listings explain the omission."
        )


def test_dexto_is_global_only_by_construction(rows):
    """dexto: adapter raises ValueError at project scope; matrix entry documents global-only."""
    import pytest

    from agent_toolkit_cli.agent_adapters import get_adapter
    from agent_toolkit_cli.skill_agents import AGENTS

    cfg = AGENTS["dexto"]
    assert cfg.subagent_mechanism == "config_file_folder", (
        "dexto must be enabled (PR4); if reverted, fix the catalog."
    )
    adapter = get_adapter("dexto")
    with pytest.raises(ValueError, match="(?i)global.only|dexto"):
        adapter.destination("any-slug", scope="project", project=None)


def test_pr4_disabled_set_is_two_cells():
    """PR2_DISABLED_DESPITE_MATRIX_SUPPORT must contain exactly {codex, firebender}.

    Locks the PR4 reduction from 4 → 2. If aider-desk or dexto are re-added to
    the disabled set, this test fails before the install-machinery tests run.
    """
    assert PR2_DISABLED_DESPITE_MATRIX_SUPPORT == frozenset({"codex", "firebender"}), (
        f"Expected disabled set {{codex, firebender}}, got "
        f"{PR2_DISABLED_DESPITE_MATRIX_SUPPORT}. "
        "aider-desk + dexto were enabled in PR4 and must not be re-disabled here."
    )
