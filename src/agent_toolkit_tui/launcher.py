"""Click dispatch shared by TUI entry points and shell completion."""
from __future__ import annotations

from pathlib import Path
import sys

import click

from agent_toolkit_cli.commands.completion import completion
from agent_toolkit_cli.commands.update import update
from agent_toolkit_tui import __version__


@click.group(invoke_without_command=True)
@click.version_option(__version__, "--version", "-V", prog_name="agent-toolkit-tui")
@click.pass_context
def launcher(ctx: click.Context) -> None:
    """Open the Toolkit TUI, or configure completion/update both applications."""
    if ctx.invoked_subcommand is None:
        from agent_toolkit_tui.app import TUIApp
        TUIApp().run()


launcher.add_command(update)
launcher.add_command(completion)


def main() -> int:
    try:
        launcher.main(args=sys.argv[1:], prog_name=Path(sys.argv[0]).name, standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        raise SystemExit(exc.exit_code) from exc
    except click.Abort as exc:
        click.echo("Aborted!", err=True)
        raise SystemExit(1) from exc
    return 0
