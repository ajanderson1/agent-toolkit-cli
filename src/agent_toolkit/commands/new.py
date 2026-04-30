"""`agent-toolkit new` — scaffold a new asset with valid v1alpha1 frontmatter."""
from __future__ import annotations

import json
from pathlib import Path

import click

from agent_toolkit._ui import header, summary

_KIND_LAYOUT = {
    "skill": ("skills/{slug}/SKILL.md", "markdown"),
    "agent": ("agents/{slug}.md", "markdown"),
    "command": ("commands/{slug}.md", "markdown"),
    "hook": ("hooks/{slug}.meta.yaml", "yaml"),
    "mcp": ("mcps/{slug}/mcp.json", "json"),
    "plugin": ("plugins/{slug}/marketplace.json", "json"),
}


_FRONTMATTER_TEMPLATE = """---
apiVersion: agent-toolkit/v1alpha1
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


@click.command(name="new", short_help="Scaffold a new asset with valid v1alpha1 frontmatter.")
@click.argument("kind", type=click.Choice(list(_KIND_LAYOUT)))
@click.argument("slug")
@click.option(
    "--repo-root",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Repo root to write into (defaults to current directory).",
)
def new(kind: str, slug: str, repo_root: str) -> None:
    """Create a new asset of the given kind at the canonical path with valid
    v1alpha1 frontmatter. The file is created with TODO placeholders; edit
    them, then run `agent-toolkit check` to validate.
    """
    header(f"Scaffolding new {kind} '{slug}'...")
    root = Path(repo_root).resolve()
    layout, fmt = _KIND_LAYOUT[kind]
    target = root / layout.format(slug=slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise click.UsageError(f"{target} already exists")
    if fmt == "markdown":
        target.write_text(_FRONTMATTER_TEMPLATE.format(slug=slug))
    elif fmt == "yaml":
        target.write_text(
            f"apiVersion: agent-toolkit/v1alpha1\n"
            f"metadata:\n"
            f"  name: {slug}\n"
            f"  description: TODO ending with period.\n"
            f"  lifecycle: experimental\n"
            f"spec:\n"
            f"  origin: first-party\n"
            f"  vendored_via: none\n"
            f"  harnesses:\n"
            f"    - claude\n"
        )
    elif fmt == "json":
        target.write_text(
            json.dumps(
                {
                    "agent_toolkit": {
                        "apiVersion": "agent-toolkit/v1alpha1",
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
