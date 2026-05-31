"""`pi-extension doctor [-g/-p] [--no-fix]` — diagnose and (optionally) repair
pi-extension installation drift.

Detects:
  - missing store copies (lock entry but no directory)
  - drifted symlinks (symlink points to wrong target)
  - stray symlinks (in extensions/ but not in the lock)
  - dirty working trees (uncommitted changes in the store copy)
  - orphaned override entries (extensions[] entries whose path is missing)

extensions[] OBSERVE-ONLY guarantee:
  Doctor reads extensions[] to detect orphaned overrides, but it NEVER
  adds, removes, edits, or reorders any entry in extensions[]. The
  fix_action for orphaned-override findings is always None (report-only).
  See pi_extension_doctor.py for the 0.77.0 fact-check finding on
  extensions[] semantics.
"""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_doctor import diagnose


@click.command("doctor")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--no-fix", is_flag=True, help="Report only; do not prompt or mutate.")
@click.pass_context
def doctor_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
    no_fix: bool,
) -> None:
    """Diagnose and (optionally) repair pi-extension installation drift.

    extensions[] entries are always observe-only — doctor reports orphaned
    override entries but never modifies settings.json extensions[].
    """
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    findings = diagnose(
        slugs=slugs or None,
        scope=scope, home=home, project=project_root,
    )

    if not findings:
        click.echo("all clean")
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
        try:
            ans = click.prompt(
                "  apply?", default="N", show_default=False,
                type=click.Choice(["y", "N", "q"], case_sensitive=False),
            )
        except (click.Abort, EOFError, OSError):
            click.echo("\n  (no input available — stopping; nothing applied)")
            quit_loop = True
            skipped += 1
            continue
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
    if skipped > 0 or fixed < len(findings):
        ctx.exit(1)
