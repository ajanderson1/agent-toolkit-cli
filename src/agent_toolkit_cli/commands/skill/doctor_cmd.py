"""skill doctor subcommand."""
from __future__ import annotations

import click

from agent_toolkit_cli.skill_doctor import diagnose

from ._common import scope_and_roots


@click.command("doctor")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--no-fix", is_flag=True,
              help="Report only; do not prompt or mutate.")
@click.option("--repair-foreign", is_flag=True,
              help="Allow fixing foreign symlinks (off by default).")
@click.pass_context
def doctor_cmd(
    ctx: click.Context, slugs: tuple[str, ...],
    global_: bool, project_flag: bool,
    no_fix: bool, repair_foreign: bool,
) -> None:
    """Diagnose and (optionally) repair skill-installation drift."""
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    findings = diagnose(
        slugs=slugs or None,
        scope=scope, home=home, project=project_root,
        repair_foreign=repair_foreign,
    )
    if not findings:
        click.echo("✓ all clean")
        return

    fixed = skipped = 0
    quit_loop = False
    for f in findings:
        click.echo("")
        click.echo(f"{f.slug} · {f.kind} ({f.scope})")
        click.echo(f"  path:   {f.path}")
        click.echo(f"  detail: {f.detail}")
        if f.fix_action is None or no_fix or quit_loop:
            skipped += 1
            if f.fix_action is None:
                click.echo("  (report-only — no automatic fix)")
            continue
        click.echo(f"  fix:    {f.fix_action.shell_preview}")
        ans = click.prompt(
            "  apply?", default="N", show_default=False,
            type=click.Choice(["y", "N", "q"], case_sensitive=False),
        )
        ans = ans.lower()
        if ans == "y":
            try:
                f.fix_action.apply()
                click.echo("  fixed.")
                fixed += 1
            except Exception as exc:
                click.echo(f"  fix failed: {exc}")
                skipped += 1
        elif ans == "q":
            quit_loop = True
            skipped += 1
        else:
            skipped += 1

    click.echo("")
    click.echo(
        f"summary: {len(findings)} findings, {fixed} fixed, {skipped} skipped"
    )
    if skipped > 0:
        ctx.exit(1)
