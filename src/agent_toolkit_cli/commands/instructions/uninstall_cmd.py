import click


@click.command(help="Remove our pointers; leave foreign files alone.")
def uninstall_cmd() -> None:
    raise click.ClickException("not yet implemented (Task 10)")
