"""`agent install <slug> [-g/-p] [--harnesses <names>]` — project to harnesses.

Projects the agent's content file into each requested harness's agents dir
via the per-mechanism adapter. When --harnesses is omitted the default is
covered-aware (#361): the standard slot plus every enabled adapter
(subagent_mechanism != 'none') the slot does NOT already cover at this scope.

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
from agent_toolkit_cli.commands.agent._common import parse_harness_tokens, scope_and_roots
from agent_toolkit_cli.skill_agents import AGENTS


def _default_harnesses(scope: str) -> tuple[str, ...]:
    """Covered-aware default install fan-out (#361): the standard slot first,
    then every enabled harness NOT covered by it at this scope, sorted.

    Covered harnesses (agents_standard_covered) read the standard slot
    natively — a per-harness own-dir copy would be a redundant second
    artifact. NOTE the deliberate asymmetry with uninstall: the no-flag
    UNINSTALL default stays MAXIMAL (no covered filter) because pre-#361
    installs wrote real own-dir files for covered harnesses — see
    uninstall_cmd._resolve_harnesses_for_uninstall.
    """
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
    from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    covered = agents_standard_covered(scope)
    result = []
    for name, cfg in AGENTS.items():
        if cfg.subagent_mechanism == "none":
            continue
        if name in covered:
            continue
        try:
            get_adapter(name)
            result.append(name)
        except (UnsupportedMechanismError, UnknownAgentError):
            # Known not-installable states only (PM review F7) — a genuinely
            # broken adapter must fail loud, not silently drop the harness.
            pass
    return ("standard", *sorted(result))


def _resolve_harnesses(harnesses_str: str | None, scope: str) -> tuple[str, ...]:
    """Expand comma-separated harness names or return scope-aware defaults.

    Explicit values go through the shared parse/normalize/dedupe seam
    (_common.parse_harness_tokens): synthetic catalog names rejected,
    claude-code normalized to standard, order-preserving dedupe.
    """
    if harnesses_str is None:
        return _default_harnesses(scope)
    return parse_harness_tokens(harnesses_str)


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
    help="Comma-separated harness names. Default: standard + all enabled "
         "harnesses not covered by the standard slot.",
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
    # also counts. Either is sufficient to proceed — at GLOBAL scope. PROJECT
    # scope additionally requires a global lock entry (#362, below).
    from agent_toolkit_cli.agent_paths import canonical_agent_dir as _cad
    global_lock = read_lock(library_lock_path())
    global_canonical = _cad(slug, scope="global")
    if slug not in global_lock.skills and not global_canonical.exists():
        raise click.ClickException(
            f"{slug}: not in the global library; run `agent add` first"
        )

    # #362: a project install derives its project lock entry from the
    # GLOBAL lock entry — require it before seeding the project canonical
    # so a doomed install leaves no residue. Exempt slugs already in the
    # project lock (#360 "unlisted" entries reinstall without a library
    # entry). apply() re-checks this; the duplicate here is purely to
    # fail before the copytree.
    if scope == "project" and project is not None:
        from agent_toolkit_cli.agent_paths import lock_file_path
        project_lock = read_lock(
            lock_file_path(scope="project", project=project)
        )
        if (
            slug not in project_lock.skills
            and slug not in global_lock.skills
        ):
            raise click.ClickException(
                f"{slug}: no global lock entry; run `agent add {slug}` first"
            )

    try:
        target_harnesses = _resolve_harnesses(harnesses, scope)
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
