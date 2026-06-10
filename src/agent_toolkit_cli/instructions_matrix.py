"""Harness-matrix parser for the instructions kind (moved from
commands/instructions/list_cmd.py for reuse by the TUI's standard-coverage
panel, #351 — list_cmd imports it back).

The harness matrix is the human-facing SSOT at <repo-root>/docs/agent-toolkit/
harness-matrix.md. It is force-included into the wheel as package data
(see pyproject.toml) so packaged installs can read it via importlib.resources
(#305). Editable/source-tree runs don't materialise that package data, so we
fall back to the repo-relative doc. This module is at src/agent_toolkit_cli/;
parents[2] is the repo root (recomputed from list_cmd's parents[4] — the
#305/#308 packaged-path-gap class).
"""
from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

_DATA_PACKAGE = "agent_toolkit_cli.data"
_MATRIX_FILENAME = "harness-matrix.md"
_SOURCE_TREE_MATRIX = Path(__file__).resolve().parents[2] / "docs/agent-toolkit/harness-matrix.md"
_SECTION_HEADING = "## Instruction-file (`instructions` kind) support — all harnesses"
_ROW_RE = re.compile(
    r"^\|\s*`(?P<harness>[a-z][a-z0-9-]*)`\s*\|"
    r"(?P<verdict>[^|]+)\|"
    r"(?P<default>[^|]*)\|"
    r"(?P<paths>[^|]*)\|"
)


def _read_matrix_text() -> str:
    """Read the harness matrix, preferring packaged data over the source tree.

    Packaged installs (wheels) get the matrix via importlib.resources; editable
    dev installs, where the force-included package data is not materialised on
    disk, fall back to the repo-relative doc. Fails loud naming both locations
    if neither is reachable.
    """
    try:
        packaged = resources.files(_DATA_PACKAGE) / _MATRIX_FILENAME
        return packaged.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    if _SOURCE_TREE_MATRIX.is_file():
        return _SOURCE_TREE_MATRIX.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "harness-matrix.md not found as packaged data "
        "(agent_toolkit_cli/data/harness-matrix.md) nor in the source tree "
        f"({_SOURCE_TREE_MATRIX}). The wheel must force-include the matrix; "
        "see pyproject.toml [tool.hatch.build.targets.wheel.force-include]."
    )


def instructions_matrix_rows() -> list[dict[str, str]]:
    """Parse the instructions-kind section into per-harness verdict rows."""
    text = _read_matrix_text()
    section = text.split(_SECTION_HEADING, 1)[1]
    section = re.split(r"^## ", section, maxsplit=1, flags=re.MULTILINE)[0]
    rows: list[dict[str, str]] = []
    for line in section.splitlines():
        m = _ROW_RE.match(line.strip())
        if m is None:
            continue
        rows.append({
            "harness": m.group("harness"),
            "verdict": m.group("verdict").strip(),
            "default_file": m.group("default").strip(),
            "paths": m.group("paths").strip(),
        })
    rows.sort(key=lambda r: r["harness"])
    return rows
