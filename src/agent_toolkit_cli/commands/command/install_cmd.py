from __future__ import annotations
from pathlib import Path
import click
from agent_toolkit_cli import command_install
from agent_toolkit_cli._install_core import InstallError, InstallPlan
from agent_toolkit_cli.command_lock import read_lock
from agent_toolkit_cli.command_paths import canonical_command_dir, library_lock_path
from agent_toolkit_cli.commands.command._common import DEFAULT_COMMAND_HARNESSES, parse_harness_tokens, scope_and_roots, validate_slug


@click.command("install")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--harnesses", default=None, help="Comma-separated harness names. Default: claude-code,pi,gemini-cli.")
@click.pass_context
def install_cmd(ctx, slug, global_, project_flag, harnesses):
    """Project a command into harness command slots."""
    slug = validate_slug(slug)
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None)
    global_lock = read_lock(library_lock_path())
    if slug not in global_lock.skills and not canonical_command_dir(slug, scope="global").exists():
        raise click.ClickException(f"{slug}: not in the global library; run `command add` first")
    targets = parse_harness_tokens(harnesses) if harnesses is not None else DEFAULT_COMMAND_HARNESSES
    if "codex" in targets:
        click.echo("warning: Codex custom prompts are deprecated", err=True)
    if scope == "project" and project is not None:
        canonical = canonical_command_dir(slug, scope="project", project=project)
        if not canonical.exists():
            src = canonical_command_dir(slug, scope="global")
            if src.exists():
                import shutil
                canonical.parent.mkdir(parents=True, exist_ok=True)
                if src.is_symlink():
                    canonical.symlink_to(src.resolve(), target_is_directory=True)
                else:
                    shutil.copytree(src, canonical, symlinks=True)
    p = InstallPlan(slug=slug, scope=scope, source=None, ref=None, add_agents=targets, remove_agents=())
    try:
        result = command_install.apply(p, home=home or (Path.home() if scope == "global" else None), project=project)
    except (InstallError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    for path in result.created:
        click.echo(f"  projected {path}")
    click.echo(f"installed {slug} [{scope}]")
