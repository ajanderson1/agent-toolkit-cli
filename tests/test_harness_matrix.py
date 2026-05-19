"""Parity test: harness-matrix.md doc must agree with the code.

Parses docs/agent-toolkit/harness-matrix.md and cross-references against:
  - agent_toolkit_cli._support._USER_TARGETS  (symlink-projected pairs)
  - agent_toolkit_cli.harness_adapters        (adapter-driven pairs)

All assertions name the offending (harness, kind) cell, the doc value, and
the code value so failures are immediately actionable.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent_toolkit_cli._support import _USER_TARGETS, ALL_HARNESSES, ALL_KINDS
from agent_toolkit_cli._translators import TRANSLATORS
from agent_toolkit_cli.harness_adapters import get_adapter
from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

# ---------------------------------------------------------------------------
# Locate the doc
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_DOC_PATH = _REPO_ROOT / "docs" / "agent-toolkit" / "harness-matrix.md"

# ---------------------------------------------------------------------------
# Allowed mechanism strings (must match the "Mechanisms" section exactly)
# ---------------------------------------------------------------------------

VALID_MECHANISMS = frozenset(
    [
        "symlink",
        "config_file",
        "config_file+folder",
        "plugin_folder",
        "translate",
        "dual-symlink",
        "unsupported (gap)",
        "unsupported (by design)",
    ]
)

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Column order matches the matrix header: Claude | Codex | OpenCode | Gemini | Pi
_HARNESS_ORDER = ("claude", "codex", "opencode", "gemini", "pi")

# Row pattern: | **<kind>** | <claude_cell> | <codex_cell> | <opencode_cell> | <gemini_cell> | <pi_cell> |
_ROW_RE = re.compile(
    r"^\|\s*\*\*(?P<kind>[a-z][a-z0-9-]*)\*\*\s*\|"
    r"(?P<claude>[^|]+)\|"
    r"(?P<codex>[^|]+)\|"
    r"(?P<opencode>[^|]+)\|"
    r"(?P<gemini>[^|]+)\|"
    r"(?P<pi>[^|]+)\|"
)


def _parse_matrix(doc_path: Path) -> dict[tuple[str, str], str]:
    """Return {(harness, kind): raw_cell_text} from the matrix table.

    Raises FileNotFoundError when the doc is missing.
    """
    text = doc_path.read_text(encoding="utf-8")
    result: dict[tuple[str, str], str] = {}
    for line in text.splitlines():
        m = _ROW_RE.match(line.strip())
        if m is None:
            continue
        kind = m.group("kind")
        for harness in _HARNESS_ORDER:
            cell = m.group(harness).strip()
            result[(harness, kind)] = cell
    return result


def _cell_mechanism(cell: str) -> str | None:
    """Extract the leading mechanism keyword from a cell string.

    Returns None if no recognised keyword is found.
    """
    cell_lower = cell.lower()
    # Longer matches first to avoid partial matches.
    for mech in sorted(VALID_MECHANISMS, key=len, reverse=True):
        if cell_lower.startswith(mech):
            return mech
    return None


def _cell_target_path(cell: str) -> str | None:
    """Extract the path following a `→` arrow in the cell, if present."""
    if "→" not in cell:
        return None
    after_arrow = cell.split("→", 1)[1].strip()
    # Strip backtick-wrapped path if present.
    after_arrow = after_arrow.strip("`").split("`")[0]
    return after_arrow.strip()


# ---------------------------------------------------------------------------
# Fixtures / module-level setup
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def matrix() -> dict[tuple[str, str], str]:
    """Parsed (harness, kind) → raw_cell from the doc."""
    assert _DOC_PATH.exists(), (
        f"harness-matrix.md not found at {_DOC_PATH}. "
        "Create docs/agent-toolkit/harness-matrix.md before running this test."
    )
    return _parse_matrix(_DOC_PATH)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDocExists:
    def test_doc_file_present(self):
        assert _DOC_PATH.exists(), (
            f"Expected {_DOC_PATH} to exist. "
            "Run Phase 1C to create docs/agent-toolkit/harness-matrix.md."
        )

    def test_doc_has_matrix_rows(self, matrix):
        assert len(matrix) > 0, "Matrix parse returned no rows — check the table format."

    def test_all_kinds_covered(self, matrix):
        """Every kind in ALL_KINDS must appear in the parsed matrix."""
        parsed_kinds = {kind for _, kind in matrix.keys()}
        missing = set(ALL_KINDS) - parsed_kinds
        assert not missing, (
            f"Kinds {missing} are listed in ALL_KINDS but absent from the "
            "harness-matrix.md table."
        )

    def test_all_harnesses_covered(self, matrix):
        """Every harness in ALL_HARNESSES must appear in the parsed matrix."""
        parsed_harnesses = {harness for harness, _ in matrix.keys()}
        missing = set(ALL_HARNESSES) - parsed_harnesses
        assert not missing, (
            f"Harnesses {missing} are listed in ALL_HARNESSES but absent from the "
            "harness-matrix.md table."
        )


class TestMechanismStrings:
    def test_all_cells_use_valid_mechanism_strings(self, matrix):
        """Every cell must start with a recognised mechanism keyword."""
        bad: list[tuple[str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            mech = _cell_mechanism(cell)
            if mech is None:
                bad.append((harness, kind, cell))
        assert not bad, (
            "The following cells use unrecognised mechanism strings "
            "(check for typos against the Mechanisms section):\n"
            + "\n".join(
                f"  ({h!r}, {k!r}): {c!r}" for h, k, c in bad
            )
        )


class TestSymlinkParity:
    def test_every_symlink_cell_has_user_target_entry(self, matrix):
        """Every cell marked 'symlink' must have a corresponding _USER_TARGETS key."""
        bad: list[tuple[str, str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            if _cell_mechanism(cell) != "symlink":
                continue
            if (harness, kind) not in _USER_TARGETS:
                bad.append((harness, kind, cell, "missing from _USER_TARGETS"))
        assert not bad, (
            "Doc says 'symlink' but _USER_TARGETS has no entry:\n"
            + "\n".join(
                f"  ({h!r}, {k!r}): doc={c!r} — {reason}"
                for h, k, c, reason in bad
            )
        )

    def test_symlink_cell_path_matches_user_target(self, matrix):
        """The path fragment after → in a symlink cell must be a substring of
        the _USER_TARGETS value (case-insensitive)."""
        bad: list[tuple[str, str, str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            if _cell_mechanism(cell) != "symlink":
                continue
            if (harness, kind) not in _USER_TARGETS:
                continue  # caught by test_every_symlink_cell_has_user_target_entry
            doc_path = _cell_target_path(cell)
            if doc_path is None:
                # No → in cell — skip path match, the previous test covers presence.
                continue
            code_path = _USER_TARGETS[(harness, kind)]
            # Normalise: strip {home}/ prefix and trailing slash for comparison.
            code_path_stripped = code_path.replace("{home}/", "").rstrip("/")
            doc_path_stripped = doc_path.lstrip("~/").rstrip("/")
            # The slug placeholder (<slug>/) is a suffix — strip it.
            doc_path_stripped = re.sub(r"/<slug>/?\S*$", "", doc_path_stripped)
            if doc_path_stripped.lower() not in code_path_stripped.lower():
                bad.append((harness, kind, doc_path, code_path, code_path_stripped))
        assert not bad, (
            "Symlink cell path does not match _USER_TARGETS value:\n"
            + "\n".join(
                f"  ({h!r}, {k!r}): doc_path={dp!r}, "
                f"code_path={cp!r} (normalised: {cpn!r})"
                for h, k, dp, cp, cpn in bad
            )
        )

    def test_every_user_target_entry_has_symlink_cell(self, matrix):
        """Every (harness, kind) in _USER_TARGETS must have a 'symlink',
        'translate', or 'config_file+folder' cell in the doc.

        Translate cells land in _USER_TARGETS because they share the same slot
        directories; only the projection mechanism differs (cache + symlink
        instead of direct symlink). config_file+folder cells also land in
        _USER_TARGETS because the adapter manages a sub-folder of artefacts
        alongside the config file — the folder path is tracked here. All three
        mechanism strings are valid here.
        """
        bad: list[tuple[str, str, str]] = []
        for (harness, kind) in sorted(_USER_TARGETS.keys()):
            cell = matrix.get((harness, kind))
            if cell is None:
                bad.append((harness, kind, "pair not found in matrix at all"))
                continue
            mech = _cell_mechanism(cell)
            if mech not in {"symlink", "translate", "config_file+folder", "dual-symlink"}:
                bad.append(
                    (
                        harness,
                        kind,
                        f"doc says {mech!r}, expected 'symlink', 'translate', or "
                        "'config_file+folder'",
                    )
                )
        assert not bad, (
            "_USER_TARGETS has entries the doc does not mark as 'symlink', 'translate', "
            "or 'config_file+folder':\n"
            + "\n".join(
                f"  ({h!r}, {k!r}): {reason}" for h, k, reason in bad
            )
        )


class TestAdapterParity:
    def test_config_file_and_plugin_folder_cells_have_real_adapters(self, matrix):
        """Every cell marked config_file or plugin_folder must have an
        implemented adapter (not UnimplementedAdapter)."""
        adapter_mechanisms = {"config_file", "plugin_folder", "config_file+folder"}
        bad: list[tuple[str, str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            mech = _cell_mechanism(cell)
            if mech not in adapter_mechanisms:
                continue
            try:
                adapter = get_adapter(harness, kind)
            except ValueError as exc:
                bad.append((harness, kind, cell, f"get_adapter raised: {exc}"))
                continue
            if isinstance(adapter, UnimplementedAdapter):
                bad.append(
                    (
                        harness,
                        kind,
                        cell,
                        f"get_adapter({harness!r}) returned UnimplementedAdapter — "
                        "no real adapter registered yet",
                    )
                )
        assert not bad, (
            "Doc marks pair as config_file/plugin_folder but no real adapter exists:\n"
            + "\n".join(
                f"  ({h!r}, {k!r}): doc={c!r} — {reason}"
                for h, k, c, reason in bad
            )
        )

    def test_adapter_strategy_matches_doc_cell(self, matrix):
        """When a real adapter exists, its .strategy attribute must match the
        mechanism string in the doc cell."""
        adapter_mechanisms = {"config_file", "plugin_folder", "config_file+folder"}
        bad: list[tuple[str, str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            mech = _cell_mechanism(cell)
            if mech not in adapter_mechanisms:
                continue
            try:
                adapter = get_adapter(harness, kind)
            except ValueError:
                continue  # already caught above
            if isinstance(adapter, UnimplementedAdapter):
                continue  # already caught above
            if getattr(adapter, "strategy", None) != mech:
                bad.append(
                    (
                        harness,
                        kind,
                        f"doc={mech!r}",
                        f"adapter.strategy={adapter.strategy!r}",
                    )
                )
        assert not bad, (
            "Adapter strategy does not match doc mechanism:\n"
            + "\n".join(
                f"  ({h!r}, {k!r}): {dv} vs {cv}" for h, k, dv, cv in bad
            )
        )


_TRANSLATE_PATH_RE = re.compile(
    r"(agents/<slug>\.md|agents/<slug>\.toml|commands/<slug>\.md|commands/<slug>\.toml|"
    r"skills/<slug>/SKILL\.md)\s*$"
)


class TestTranslateParity:
    def test_every_translate_cell_has_translator_entry(self, matrix):
        bad: list[tuple[str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            if _cell_mechanism(cell) != "translate":
                continue
            if (harness, kind) not in TRANSLATORS:
                bad.append((harness, kind, cell))
        assert not bad, (
            "Doc says 'translate' but TRANSLATORS has no entry:\n"
            + "\n".join(f"  ({h!r}, {k!r}): {c!r}" for h, k, c in bad)
        )

    def test_every_translator_entry_has_translate_cell(self, matrix):
        bad: list[tuple[str, str, str]] = []
        for (harness, kind) in sorted(TRANSLATORS.keys()):
            cell = matrix.get((harness, kind))
            if cell is None:
                bad.append((harness, kind, "pair not in matrix"))
                continue
            mech = _cell_mechanism(cell)
            if mech != "translate":
                bad.append((harness, kind, f"doc says {mech!r}, expected 'translate'"))
        assert not bad, (
            "TRANSLATORS has entries the doc does not mark as 'translate':\n"
            + "\n".join(f"  ({h!r}, {k!r}): {reason}" for h, k, reason in bad)
        )

    def test_translate_cell_path_matches_slot_convention(self, matrix):
        """Every `translate` cell's `→ <path>` fragment names a slot path
        ending in `agents/<slug>.md` or `commands/<slug>.md`."""
        bad: list[tuple[str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            if _cell_mechanism(cell) != "translate":
                continue
            doc_path = _cell_target_path(cell)
            if doc_path is None:
                bad.append((harness, kind, f"no `→` arrow in cell: {cell!r}"))
                continue
            if not _TRANSLATE_PATH_RE.search(doc_path):
                bad.append((harness, kind, f"path does not match convention: {doc_path!r}"))
        assert not bad, (
            "Translate cell path does not match `agents/<slug>.md` or `commands/<slug>.md`:\n"
            + "\n".join(f"  ({h!r}, {k!r}): {reason}" for h, k, reason in bad)
        )
