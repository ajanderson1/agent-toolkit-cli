"""`agent install <slug> [-g/-p] [--harnesses <names>]` — project to harnesses.

Projects the agent's content file into each requested harness's agents dir
via the per-mechanism adapter. Harnesses default to all enabled adapters
(subagent_mechanism != 'none') when --harnesses is omitted.

result.removed is NOT populated by apply() (the uninstall loop in
agent_install.apply() never appends — see code comment there). We do NOT
rely on result.removed for output; instead we report from plan.add_agents.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import agent_install
from agent_toolkit_cli._install_core import InstallError, InstallPlan
from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import canonical_agent_dir, library_lock_path
from agent_toolkit_cli.commands.agent._common import scope_and_roots
from agent_toolkit_cli.skill_agents import AGENTS, resolve_agent_token


def _default_harnesses() -> tuple[str, ...]:
    """Return all harness names whose subagent_mechanism != 'none'."""
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
    result = []
    for name, cfg in AGENTS.items():
        if cfg.subagent_mechanism == "none":
            continue
        try:
            get_adapter(name)
            result.append(name)
        except (UnsupportedMechanismError, Exception):
            pass
    return tuple(sorted(result))


def _resolve_harnesses(harnesses_str: str | None) -> tuple[str, ...]:
    """Expand comma-separated harness names or return defaults."""
    if harnesses_str is None:
        return _default_harnesses()
    parts = [resolve_agent_token(p.strip()) for p in harnesses_str.split(",") if p.strip()]
    unknown = [p for p in parts if p not in AGENTS]
    if unknown:
        raise click.UsageError(f"unknown harness(es): {', '.join(unknown)}")
    return tuple(parts)


@click.command("install", epilog="""\
Examples:

\b
  agent-toolkit-cli agent install my-agent -g
  agent-toolkit-cli agent install my-agent -p
  agent-toolkit-cli agent install my-agent -g --harnesses claude-code,gemini-cli
""")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option(
    "--harnesses", default=None,
    help="Comma-separated harness names. Default: all enabled harnesses.",
)
@click.pass_context
def install_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
    harnesses: str | None,
) -> None:
    """Project an agent into the chosen scope's harnesses."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )

    # Verify the slug exists in the global library (canonical or lock entry).
    # We check BOTH the lock file and the canonical directory: a slug that
    # has been `agent add`-ed has a lock entry; a manually-seeded canonical
    # also counts. Either is sufficient to proceed.
    from agent_toolkit_cli.agent_paths import canonical_agent_dir as _cad
    global_lock = read_lock(library_lock_path())
    global_canonical = _cad(slug, scope="global")
    if slug not in global_lock.skills and not global_canonical.exists():
        raise click.ClickException(
            f"{slug}: not in the global library; run `agent add` first"
        )

    try:
        target_harnesses = _resolve_harnesses(harnesses)
    except click.UsageError:
        raise

    if not target_harnesses:
        click.echo(f"{slug}: no enabled harnesses; nothing to do")
        return

    # For project scope, seed the canonical if not already present.
    if scope == "project" and project is not None:
        canonical = canonical_agent_dir(slug, scope="project", project=project)
        if not canonical.exists():
            global_canonical = canonical_agent_dir(slug, scope="global")
            if global_canonical.exists():
                import shutil
                canonical.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(global_canonical, canonical)
            else:
                raise click.ClickException(
                    f"{slug}: global canonical missing; re-run `agent add {slug}` first"
                )

    p = InstallPlan(
        slug=slug, scope=scope, source=None, ref=None,
        add_agents=target_harnesses, remove_agents=(),
    )
    # Pass explicit home=Path.home() for global scope so adapters can resolve
    # {HOME} path templates (home=None causes ValueError in symlink._expand).
    effective_home = home if home is not None else (Path.home() if scope == "global" else None)
    try:
        result = agent_install.apply(p, home=effective_home, project=project)
    except InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    for path in result.created:
        click.echo(f"  projected {path}")
    if result.skipped:
        click.echo(f"  skipped (unsupported mechanism): {', '.join(result.skipped)}")
    click.echo(f"installed {slug} [{scope}]")
