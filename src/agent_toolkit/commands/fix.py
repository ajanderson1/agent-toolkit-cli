"""`agent-toolkit fix` — regenerate auto-generated regions."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit._ui import header, summary
from agent_toolkit.generators.component_table import render_component_table
from agent_toolkit.generators.markers import inject_region
from agent_toolkit.generators.submodule_table import render_submodule_table
from agent_toolkit.schema import Validator
from agent_toolkit.walker import discover_assets

_REGION_GENERATORS = ("component-table", "submodule-table")


@click.command(short_help="Regenerate AGENTS.md auto-regions.")
@click.option(
    "--toolkit-repo",
    "toolkit_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the agent-toolkit repo (defaults to group --toolkit-repo / env / walk-up / ~/GitHub/agent-toolkit).",
)
@click.option(
    "--only",
    "only",
    default=None,
    type=click.Choice(_REGION_GENERATORS),
    help="Regenerate only this region; default regenerates all.",
)
@click.option(
    "--to-stdout",
    is_flag=True,
    help="Print the rebuilt AGENTS.md to stdout without modifying the file.",
)
@click.pass_context
def fix(ctx: click.Context, toolkit_root: Path | None, only: str | None, to_stdout: bool) -> None:
    """Regenerate the BEGIN/END marker-bounded regions inside AGENTS.md
    (component-table and submodule-table). With --to-stdout, prints the
    result without touching the file.
    """
    header("Regenerating AGENTS.md auto-regions...")
    if toolkit_root is None:
        toolkit_root = (ctx.obj or {}).get("toolkit_root")
    if toolkit_root is None:
        toolkit_root = Path(".").resolve()
    else:
        toolkit_root = Path(toolkit_root).resolve()
    root = toolkit_root

    targets = (only,) if only in _REGION_GENERATORS else _REGION_GENERATORS
    agents_path = root / "AGENTS.md"
    text = agents_path.read_text()
    for region in targets:
        body = _render(region, root)
        text = inject_region(text, region=region, body=body)
    if to_stdout:
        click.echo(text, nl=False)
        summary(f"Rendered AGENTS.md to stdout ({len(targets)} regions, file unchanged).")
    else:
        agents_path.write_text(text)
        summary(f"Updated AGENTS.md ({len(targets)} regions).")


def _render(region: str, root: Path) -> str:
    if region == "component-table":
        validator = Validator(toolkit_root=root)
        assets = discover_assets(root)
        metadata: dict[tuple[str, str], dict] = {}
        for asset in assets:
            data = validator._load_metadata(asset)  # noqa: SLF001
            if data is not None:
                metadata[(asset.kind, asset.slug)] = data
        return render_component_table(assets, metadata)
    if region == "submodule-table":
        return render_submodule_table(root)
    raise ValueError(f"unknown region: {region}")
