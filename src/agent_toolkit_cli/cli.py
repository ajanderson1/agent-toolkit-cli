"""agent-toolkit-cli Python CLI dispatcher."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click

from agent_toolkit_cli.commands.agent import agent
from agent_toolkit_cli.commands.bundle import bundle
from agent_toolkit_cli.commands.instructions import instructions
from agent_toolkit_cli.commands.mcp import mcp
from agent_toolkit_cli.commands.pi_extension import pi_extension
from agent_toolkit_cli.commands.skill import skill


try:
    _VERSION = version("agent-toolkit")
except PackageNotFoundError:
    _VERSION = "unknown"


_ASSET_COMMAND_ALIASES = {
    "skill": "skills",
    "agent": "agents",
    "mcp": "mcps",
    "pi-extension": "pi-extensions",
    "bundle": "bundles",
    "instruction": "instructions",
}


class AssetCommandGroup(click.Group):
    """Expose plural canonical asset groups while accepting singular aliases."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command
        canonical_name = _ASSET_COMMAND_ALIASES.get(cmd_name)
        if canonical_name is None:
            return None
        return super().get_command(ctx, canonical_name)


@click.group(
    cls=AssetCommandGroup,
    help=(
        "agent-toolkit-cli — manage asset collections via per-kind libraries "
        "and lockfiles. Run `agent-toolkit-cli skills --help` for subcommands.\n\n"
        "Pre-v2 commands (check, link, etc.) were removed in v2.3.0. "
        "The frozen v1 surface lives at the v1.0.0 tag; install it via "
        "`uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`."
    )
)
@click.version_option(_VERSION, "--version", "-V", prog_name="agent-toolkit-cli")
@click.option(
    "--project",
    "project_root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Path to the consumer project (default: CWD).",
)
@click.pass_context
def main(ctx: click.Context, project_root: Path | None) -> None:
    """agent-toolkit-cli."""
    ctx.ensure_object(dict)
    ctx.obj["project_root"] = Path(project_root) if project_root else None


main.add_command(skill, name="skills")
main.add_command(agent, name="agents")
main.add_command(mcp, name="mcps")
main.add_command(pi_extension, name="pi-extensions")
main.add_command(bundle, name="bundles")
main.add_command(instructions)


if __name__ == "__main__":
    main()
