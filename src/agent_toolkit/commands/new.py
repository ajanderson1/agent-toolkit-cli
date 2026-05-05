"""`agent-toolkit new` — scaffold a new asset with valid v1alpha2 frontmatter."""
from __future__ import annotations

import json
from pathlib import Path

import click

from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit._ui import header, summary

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
@click.pass_context
def new(ctx: click.Context, kind: str, slug: str, toolkit_root: Path | None) -> None:
    """Create a new asset of the given kind at the canonical path with valid
    v1alpha2 frontmatter. The file is created with TODO placeholders; edit
    them, then run `agent-toolkit check` to validate.
    """
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
    layout, fmt = _KIND_LAYOUT[kind]
    target = root / layout.format(slug=slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise click.UsageError(f"{target} already exists")
    if fmt == "mcp":
        # Two files: README.md (frontmatter) and config.json (inner MCP config).
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
        # Sibling config.json carrying the inner MCP server config.
        config_path = target.parent / "config.json"
        config_path.write_text(
            json.dumps(
                {"type": "stdio", "command": "npx", "args": ["-y", f"@TODO/{slug}"]},
                indent=2,
            ) + "\n"
        )
        rel = target.relative_to(root)
        click.echo(f"created {rel}")
        click.echo(f"created {config_path.relative_to(root)}")
        summary(f"Created {rel}. Edit it, then run 'agent-toolkit check' to validate.")
        return
    elif fmt == "markdown":
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
                    "agent_toolkit": {
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
