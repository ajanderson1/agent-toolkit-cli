"""`instructions list` — per-harness verdict from the Phase A matrix."""
from __future__ import annotations

import json as _json
import re
from pathlib import Path

import click

# list_cmd.py is at src/agent_toolkit_cli/commands/instructions/; the matrix doc
# lives at <repo-root>/docs/. parents[4] is the repo root.
_DOC = Path(__file__).resolve().parents[4] / "docs/agent-toolkit/harness-matrix.md"
_SECTION_HEADING = "## Instruction-file (`instructions` kind) support — all harnesses"
_ROW_RE = re.compile(
    r"^\|\s*`(?P<harness>[a-z][a-z0-9-]*)`\s*\|"
    r"(?P<verdict>[^|]+)\|"
    r"(?P<default>[^|]*)\|"
    r"(?P<paths>[^|]*)\|"
)


def _parse_matrix() -> list[dict[str, str]]:
    text = _DOC.read_text(encoding="utf-8")
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
