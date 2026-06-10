"""`instructions list` — per-harness verdict from the Phase A matrix.

The matrix parser lives in agent_toolkit_cli.instructions_matrix (moved
there for reuse by the TUI's standard-coverage panel, #351).
"""
from __future__ import annotations

import json as _json

import click

from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows
from agent_toolkit_cli.table import render_table


@click.command(help="Per-harness verdict for the instructions asset type.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json"]),
    default="table",
)
def list_cmd(fmt: str) -> None:
    rows = instructions_matrix_rows()
    if fmt == "json":
        click.echo(_json.dumps(rows, indent=2))
        return
    table_rows = [[r["harness"], r["verdict"], r["default_file"]] for r in rows]
    click.echo(render_table(table_rows, headers=["HARNESS", "VERDICT", "DEFAULT FILE"]))
