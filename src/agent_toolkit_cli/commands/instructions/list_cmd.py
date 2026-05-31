"""`instructions list` — per-harness verdict from the Phase A matrix."""
from __future__ import annotations

import json as _json
import re
from importlib import resources
from pathlib import Path

import click

# The harness matrix is the human-facing SSOT at <repo-root>/docs/agent-toolkit/
# harness-matrix.md. It is force-included into the wheel as package data
# (see pyproject.toml) so packaged installs can read it via importlib.resources
# (#305). Editable/source-tree runs don't materialise that package data, so we
# fall back to the repo-relative doc. list_cmd.py is at
# src/agent_toolkit_cli/commands/instructions/; parents[4] is the repo root.
_DATA_PACKAGE = "agent_toolkit_cli.data"
_MATRIX_FILENAME = "harness-matrix.md"
_SOURCE_TREE_MATRIX = Path(__file__).resolve().parents[4] / "docs/agent-toolkit/harness-matrix.md"
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


def _parse_matrix() -> list[dict[str, str]]:
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


@click.command(help="Per-harness verdict for the instructions kind.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json"]),
    default="table",
)
def list_cmd(fmt: str) -> None:
    rows = _parse_matrix()
    if fmt == "json":
        click.echo(_json.dumps(rows, indent=2))
        return
    width = max(len(r["harness"]) for r in rows)
    click.echo(f"{'HARNESS':<{width}}  VERDICT          DEFAULT FILE")
    for r in rows:
        click.echo(f"{r['harness']:<{width}}  {r['verdict']:<15}  {r['default_file']}")
