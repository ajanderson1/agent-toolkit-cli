"""`agent-toolkit new` — scaffold a new asset with valid v1alpha2 frontmatter."""
from __future__ import annotations

import json
from pathlib import Path

import click

from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli._ui import header, summary

_KIND_LAYOUT = {
    "skill": ("skills/{slug}/SKILL.md", "markdown"),
    "agent": ("agents/{slug}.md", "markdown"),
    "command": ("commands/{slug}.md", "markdown"),
    "hook": ("hooks/{slug}.meta.yaml", "yaml"),
    "mcp": ("mcps/{slug}/README.md", "mcp"),
    "plugin": ("plugins/{slug}/.claude-plugin/plugin.json", "json"),
    "pi-extension": ("extensions/{slug}/extension.meta.yaml", "yaml"),
}


_FRONTMATTER_TEMPLATE = """---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: TODO write one sentence ending with a period.
  lifecycle: experimental
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
---

# {slug}

TODO body.
"""

_SIDECAR_TEMPLATE = """apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: TODO write one sentence ending with a period.
  lifecycle: experimental
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
"""

_BODY_TEMPLATE_NO_FRONTMATTER = """# {slug}

TODO body.
"""

_MCP_SIDECAR_TEMPLATE = """apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: TODO write one sentence ending with a period.
  lifecycle: experimental
spec:
  origin: third-party
  vendored_via: none
  upstream: https://TODO
  harnesses:
    - codex
  mcp:
    transport: stdio
    install_method: npx
"""

_MCP_BODY_TEMPLATE_NO_FRONTMATTER = """# {slug}

TODO body.
"""

_SKILL_BODY_TEMPLATE = """---
name: {slug}
description: TODO write the harness-loader-facing description ending in a period.
---

# {slug}

TODO body.
"""


@click.command(name="new", short_help="Scaffold a new asset with valid v1alpha2 frontmatter.")
@click.argument("kind", type=click.Choice(list(_KIND_LAYOUT)))
@click.argument("slug")
@click.option(
    "--toolkit-repo",
    "toolkit_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the agent-toolkit repo (defaults to group --toolkit-repo / env / walk-up / ~/GitHub/agent-toolkit).",
)
@click.option(
    "--inline",
    is_flag=True,
    default=False,
    help="(mcp only) Use inline frontmatter in the body file instead of a sidecar. Skills require the two-file shape.",
)
@click.pass_context
def new(ctx: click.Context, kind: str, slug: str, toolkit_root: Path | None, inline: bool) -> None:
    """Create a new asset of the given kind at the canonical path with valid
    v1alpha2 frontmatter. The file is created with TODO placeholders; edit
    them, then run `agent-toolkit check` to validate.
    """
    if inline and kind == "skill":
        raise click.UsageError(
            "Inline frontmatter is no longer supported for skills. "
            "Skills now use a two-file shape: SKILL.md (harness frontmatter) "
            "plus <slug>.toolkit.yaml (toolkit sidecar). See "
            "docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md."
        )
    header(f"Scaffolding new {kind} '{slug}'...")
    if toolkit_root is None:
        toolkit_root = (ctx.obj or {}).get("toolkit_root")
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(explicit=None)
        except RepoNotFoundError as exc:
            raise click.ClickException(str(exc))
    else:
        toolkit_root = Path(toolkit_root).resolve()
    root = toolkit_root

    _SIDECAR_KINDS = {"skill", "mcp"}
    use_sidecar = kind in _SIDECAR_KINDS and not inline

    layout, fmt = _KIND_LAYOUT[kind]
    target = root / layout.format(slug=slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise click.UsageError(f"{target} already exists")
    if fmt == "mcp":
        from agent_toolkit_cli.walker import _KIND_ROOT

        # Always create config.json with the inner MCP server config.
        config_path = target.parent / "config.json"
        config_path.write_text(
            json.dumps(
                {"type": "stdio", "command": "npx", "args": ["-y", f"@TODO/{slug}"]},
                indent=2,
            ) + "\n"
        )
        if use_sidecar:
            # Sidecar form: write body-only README.md + sidecar .toolkit.yaml
            target.write_text(_MCP_BODY_TEMPLATE_NO_FRONTMATTER.format(slug=slug))
            sidecar = root / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"
            sidecar.write_text(_MCP_SIDECAR_TEMPLATE.format(slug=slug))
            click.echo(f"created {target.relative_to(root)}")
            click.echo(f"created {config_path.relative_to(root)}")
            click.echo(f"created {sidecar.relative_to(root)}")
            summary(f"Created {sidecar.relative_to(root)}. Edit it, then run 'agent-toolkit check' to validate.")
        else:
            # Inline form: README.md carries frontmatter.
            target.write_text(
                "---\n"
                "apiVersion: agent-toolkit/v1alpha2\n"
                "metadata:\n"
                f"  name: {slug}\n"
                "  description: TODO write one sentence ending with a period.\n"
                "  lifecycle: experimental\n"
                "spec:\n"
                "  origin: third-party\n"
                "  vendored_via: none\n"
                "  upstream: https://TODO\n"
                "  harnesses:\n"
                "    - codex\n"
                "  mcp:\n"
                "    transport: stdio\n"
                "    install_method: npx\n"
                "---\n\n"
                f"# {slug}\n\n"
                "TODO body.\n"
            )
            rel = target.relative_to(root)
            click.echo(f"created {rel}")
            click.echo(f"created {config_path.relative_to(root)}")
            summary(f"Created {rel}. Edit it, then run 'agent-toolkit check' to validate.")
        return
    elif fmt == "markdown":
        if use_sidecar:
            from agent_toolkit_cli.walker import _KIND_ROOT

            if kind == "skill":
                target.write_text(_SKILL_BODY_TEMPLATE.format(slug=slug))
            else:
                target.write_text(_BODY_TEMPLATE_NO_FRONTMATTER.format(slug=slug))
            sidecar = root / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"
            sidecar.write_text(_SIDECAR_TEMPLATE.format(slug=slug))
            click.echo(f"created {target.relative_to(root)}")
            click.echo(f"created {sidecar.relative_to(root)}")
            summary(f"Created {sidecar.relative_to(root)}. Edit it, then run 'agent-toolkit check' to validate.")
            return
        target.write_text(_FRONTMATTER_TEMPLATE.format(slug=slug))
    elif fmt == "yaml":
        default_harness = "pi" if kind == "pi-extension" else "claude"
        target.write_text(
            f"apiVersion: agent-toolkit/v1alpha2\n"
            f"metadata:\n"
            f"  name: {slug}\n"
            f"  description: TODO ending with period.\n"
            f"  lifecycle: experimental\n"
            f"spec:\n"
            f"  origin: first-party\n"
            f"  vendored_via: none\n"
            f"  harnesses:\n"
            f"    - {default_harness}\n"
        )
    elif fmt == "json":
        target.write_text(
            json.dumps(
                {
                    "agent_toolkit_cli": {
                        "apiVersion": "agent-toolkit/v1alpha2",
                        "metadata": {
                            "name": slug,
                            "description": "TODO ending with period.",
                            "lifecycle": "experimental",
                        },
                        "spec": {
                            "origin": "first-party",
                            "vendored_via": "none",
                            "harnesses": ["claude"],
                        },
                    },
                },
                indent=2,
            )
            + "\n"
        )
    rel = target.relative_to(root)
    click.echo(f"created {rel}")
    summary(f"Created {rel}. Edit it, then run 'agent-toolkit check' to validate.")
