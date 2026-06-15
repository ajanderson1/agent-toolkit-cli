"""`mcp add` — author a library entry from flags. GLOBAL-ONLY (no -p).

Exactly ONE source flag is required (--npx/--uvx/--docker/--url/--local). The
inner MCP config is derived per-method; a version is resolved best-effort
(npm view / PyPI JSON / git HEAD) and recorded as `resolved_version` for
transparency. Resolution failure is NOT an error — the entry is stored
floating and a note is printed to stderr. Re-adding an existing slug errors
(use `mcp update`).

Env var NAMES (not values) may be declared via repeatable --env; they are
stored in the sidecar so `mcp doctor` can warn when they are unset.
"""
from __future__ import annotations

import shlex
from pathlib import Path

import click

from agent_toolkit_cli.commands.mcp import _resolve
from agent_toolkit_cli.mcp_library import library_root, write_entry


def _derive_slug_npm(pkg: str) -> str:
    """`@scope/name` → `name`; `name` → `name`. Strip any version suffix."""
    base = pkg.split("@")[-1] if pkg.startswith("@") else pkg.split("@")[0]
    # `@scope/name` splits oddly on '@'; re-handle the scoped form explicitly.
    if pkg.startswith("@") and "/" in pkg:
        base = pkg.split("/", 1)[1]
    return base.rsplit("/", 1)[-1]


def _derive_slug_image(image: str) -> str:
    """`registry/owner/name:tag` → `name`."""
    no_tag = image.split(":", 1)[0]
    return no_tag.rsplit("/", 1)[-1]


def _derive_slug_url(url: str) -> str:
    """`https://host/path/name` → last non-empty path segment, else host."""
    stripped = url.rstrip("/")
    tail = stripped.rsplit("/", 1)[-1]
    # A bare https://host has no path segment to use; fall back to the host.
    if "//" in stripped and tail == stripped.split("//", 1)[1]:
        return tail.split("/", 1)[0]
    return tail or stripped


@click.command("add", epilog="""\
Examples:

\b
  agent-toolkit-cli mcp add --npx @upstash/context7-mcp --slug context7
  agent-toolkit-cli mcp add --uvx some-mcp-server
  agent-toolkit-cli mcp add --docker ghcr.io/owner/mcp:latest
  agent-toolkit-cli mcp add --url https://mcp.example.com/sse
  agent-toolkit-cli mcp add --local ./my-server --command "python server.py"
""")
@click.option("--npx", "npx_pkg", default=None, help="npm package (resolved via `npm view`).")
@click.option("--uvx", "uvx_pkg", default=None, help="PyPI package (resolved via the PyPI JSON API).")
@click.option("--docker", "docker_image", default=None, help="Docker image[:tag] (tag as given).")
@click.option("--url", "url", default=None, help="Remote MCP server URL (http transport).")
@click.option("--local", "local_dir", default=None, help="Local dir; pair with --command.")
@click.option("--command", "command", default=None, help="Command for --local (split into command+args).")
@click.option("--env", "env_vars", multiple=True, help="Declared env var NAME (repeatable; stored in sidecar).")
@click.option("--description", "description", default=None, help="Human description for the sidecar.")
@click.option("--slug", "slug", default=None, help="Override the derived slug.")
def add_cmd(
    npx_pkg: str | None,
    uvx_pkg: str | None,
    docker_image: str | None,
    url: str | None,
    local_dir: str | None,
    command: str | None,
    env_vars: tuple[str, ...],
    description: str | None,
    slug: str | None,
) -> None:
    """Author an MCP server into the global library from flags."""
    sources = {
        "--npx": npx_pkg,
        "--uvx": uvx_pkg,
        "--docker": docker_image,
        "--url": url,
        "--local": local_dir,
    }
    given = [flag for flag, value in sources.items() if value is not None]
    if len(given) == 0:
        raise click.UsageError(
            "exactly one source flag is required: --npx / --uvx / --docker / --url / --local"
        )
    if len(given) > 1:
        raise click.UsageError(
            f"only one source flag may be given; got {', '.join(given)}"
        )

    inner: dict
    install_method: str
    transport: str
    resolved_version: str | None = None
    derived_slug: str
    floating_pkg: str | None = None  # name printed in the floating note, if any
    local_source_dir: str | None = None  # absolute --local dir, for `mcp update`

    if npx_pkg is not None:
        install_method = "npx"
        transport = "stdio"
        derived_slug = _derive_slug_npm(npx_pkg)
        resolved_version = _resolve.resolve_npm_version(npx_pkg)
        pinned = f"{npx_pkg}@{resolved_version}" if resolved_version else npx_pkg
        inner = {"type": "stdio", "command": "npx", "args": ["-y", pinned]}
        if resolved_version is None:
            floating_pkg = npx_pkg
    elif uvx_pkg is not None:
        install_method = "uvx"
        transport = "stdio"
        derived_slug = uvx_pkg.rsplit("/", 1)[-1]
        resolved_version = _resolve.resolve_pypi_version(uvx_pkg)
        pinned = f"{uvx_pkg}=={resolved_version}" if resolved_version else uvx_pkg
        inner = {"type": "stdio", "command": "uvx", "args": [pinned]}
        if resolved_version is None:
            floating_pkg = uvx_pkg
    elif docker_image is not None:
        install_method = "docker"
        transport = "stdio"
        derived_slug = _derive_slug_image(docker_image)
        image = docker_image if ":" in docker_image else f"{docker_image}:latest"
        # resolved_version is the tag as given; docker tags are the version authority.
        resolved_version = image.rsplit(":", 1)[-1]
        inner = {"type": "stdio", "command": "docker", "args": ["run", "--rm", "-i", image]}
    elif url is not None:
        install_method = "url"
        transport = "http"
        derived_slug = _derive_slug_url(url)
        inner = {"type": "http", "url": url}
        # Nothing to resolve for a URL source.
    else:  # local_dir is not None
        if not command:
            raise click.UsageError("--local requires --command")
        install_method = "local"
        transport = "stdio"
        directory = Path(local_dir).expanduser().resolve()  # type: ignore[arg-type]
        derived_slug = directory.name or "local-mcp"
        parts = shlex.split(command)
        if not parts:
            raise click.UsageError("--command must contain at least the command name")
        inner = {"type": "stdio", "command": parts[0], "args": parts[1:]}
        resolved_version = _resolve.resolve_git_head_sha(directory)
        # Persist the absolute source dir so `mcp update` can refresh the HEAD
        # SHA later from any cwd (inner_config records only the command, not the
        # dir). A non-repo local dir simply has no version — stored floating, no
        # note (the user gave a path, not a package; "could not resolve" misleads).
        local_source_dir = str(directory)

    final_slug = slug or derived_slug
    if not final_slug:
        raise click.ClickException("could not derive a slug; pass --slug explicitly")

    library = library_root(Path.home())

    metadata: dict = {
        "name": final_slug,
        "install_method": install_method,
        "transport": transport,
    }
    if resolved_version is not None:
        metadata["resolved_version"] = resolved_version
    if local_source_dir is not None:
        metadata["source_dir"] = local_source_dir
    if env_vars:
        metadata["env"] = list(env_vars)
    if description is not None:
        metadata["description"] = description

    try:
        entry_dir = write_entry(
            library, final_slug, inner_config=inner, metadata=metadata
        )
    except FileExistsError as exc:
        raise click.ClickException(
            f"{final_slug} already in the library; use 'mcp update {final_slug}'"
        ) from exc

    if floating_pkg is not None:
        click.echo(
            f"note: could not resolve a version for {floating_pkg}; stored floating",
            err=True,
        )

    version_note = f" @ {resolved_version}" if resolved_version else " (floating)"
    click.echo(f"added {final_slug}{version_note} → {entry_dir}")
