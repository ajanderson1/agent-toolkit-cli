"""`mcp add` — author a manifest-first global library entry from flags.

Exactly one source flag is required. The complete authoring record is committed
to ``mcps-library.json`` before its config/sidecar materialisation is written.
Legacy physical libraries require an explicit ``mcp migrate`` first.
"""
from __future__ import annotations

import shlex
from pathlib import Path

import click

from agent_toolkit_cli.commands.mcp import _resolve
from agent_toolkit_cli.mcp_library import (
    library_root,
    materialize_entry,
    scan_entry_files,
)
from agent_toolkit_cli.mcp_manifest import (
    McpManifestEntry,
    UnsafeMcpSpecError,
    assert_safe_entry,
    manifest_path,
    read_manifest,
    write_manifest,
)


def _normalise_npm_package(package: str) -> str:
    """Drop a trailing npm version while preserving a leading scope."""
    if package.startswith("@"):
        name, separator, _version = package.rpartition("@")
        return name if separator and name else package
    return package.split("@", 1)[0]


def _normalise_pypi_package(package: str) -> str:
    """Drop a pinned ``==version`` from a uvx source token."""
    return package.split("==", 1)[0]


def _derive_slug_npm(package: str) -> str:
    """``@scope/name`` → ``name``; ``name`` → ``name``."""
    return package.rsplit("/", 1)[-1]


def _derive_slug_image(image: str) -> str:
    """``registry:port/owner/name:tag`` → ``name``."""
    leaf = image.rsplit("/", 1)[-1]
    return leaf.split("@", 1)[0].split(":", 1)[0]


def _effective_docker_image(image: str) -> tuple[str, str]:
    """Return an image with an effective tag/digest and its version token."""
    if "@" in image:
        return image, image.rsplit("@", 1)[-1]
    leaf = image.rsplit("/", 1)[-1]
    if ":" in leaf:
        return image, leaf.rsplit(":", 1)[-1]
    return f"{image}:latest", "latest"


def _derive_slug_url(url: str) -> str:
    """``https://host/path/name`` → final path segment, else host."""
    stripped = url.rstrip("/")
    tail = stripped.rsplit("/", 1)[-1]
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
    if not given:
        raise click.UsageError(
            "exactly one source flag is required: "
            "--npx / --uvx / --docker / --url / --local"
        )
    if len(given) > 1:
        raise click.UsageError(
            f"only one source flag may be given; got {', '.join(given)}"
        )

    install_method: str
    transport: str
    source: str
    authored_command: str | None
    args: tuple[str, ...]
    resolved_version: str | None = None
    floating_pkg: str | None = None

    if npx_pkg is not None:
        install_method = "npx"
        transport = "stdio"
        source = _normalise_npm_package(npx_pkg)
        derived_slug = _derive_slug_npm(source)
        resolved_version = _resolve.resolve_npm_version(source)
        pinned = f"{source}@{resolved_version}" if resolved_version else source
        authored_command = "npx"
        args = ("-y", pinned)
        if resolved_version is None:
            floating_pkg = source
    elif uvx_pkg is not None:
        install_method = "uvx"
        transport = "stdio"
        source = _normalise_pypi_package(uvx_pkg)
        derived_slug = source.rsplit("/", 1)[-1]
        resolved_version = _resolve.resolve_pypi_version(source)
        pinned = f"{source}=={resolved_version}" if resolved_version else source
        authored_command = "uvx"
        args = (pinned,)
        if resolved_version is None:
            floating_pkg = source
    elif docker_image is not None:
        install_method = "docker"
        transport = "stdio"
        source, resolved_version = _effective_docker_image(docker_image)
        derived_slug = _derive_slug_image(source)
        authored_command = "docker"
        args = ("run", "--rm", "-i", source)
    elif url is not None:
        install_method = "url"
        transport = "http"
        source = url
        derived_slug = _derive_slug_url(url)
        authored_command = None
        args = ()
    else:
        if not command:
            raise click.UsageError("--local requires --command")
        install_method = "local"
        transport = "stdio"
        directory = Path(local_dir).expanduser().resolve()  # type: ignore[arg-type]
        source = str(directory)
        derived_slug = directory.name or "local-mcp"
        parts = shlex.split(command)
        if not parts:
            raise click.UsageError("--command must contain at least the command name")
        authored_command = parts[0]
        args = tuple(parts[1:])
        resolved_version = _resolve.resolve_git_head_sha(directory)

    final_slug = slug or derived_slug
    if not final_slug:
        raise click.ClickException("could not derive a slug; pass --slug explicitly")

    entry = McpManifestEntry(
        slug=final_slug,
        install_method=install_method,
        transport=transport,
        source=source,
        command=authored_command,
        args=args,
        env=tuple(env_vars),
        description=description,
        resolved_version=resolved_version,
    )
    try:
        assert_safe_entry(entry)
    except UnsafeMcpSpecError as exc:
        raise click.ClickException(str(exc)) from exc

    home = Path.home()
    library = library_root(home)
    path = manifest_path(home)
    physical = scan_entry_files(library)
    if not path.is_file() and physical:
        raise click.ClickException(
            "MCP library manifest is missing; run: agent-toolkit-cli mcp migrate"
        )
    try:
        manifest = read_manifest(path)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if final_slug in manifest or final_slug in physical:
        raise click.ClickException(
            f"{final_slug} already in the library; use 'mcp update {final_slug}'"
        )

    try:
        write_manifest(path, {**manifest, final_slug: entry})
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        entry_dir = materialize_entry(library, entry, overwrite=False)
    except FileExistsError as exc:
        raise click.ClickException(
            f"{final_slug} already in the library; use 'mcp update {final_slug}'"
        ) from exc
    except OSError as exc:
        raise click.ClickException(
            f"manifest committed but {final_slug} materialisation failed"
        ) from exc

    if floating_pkg is not None:
        click.echo(
            f"note: could not resolve a version for {floating_pkg}; stored floating",
            err=True,
        )

    version_note = f" @ {resolved_version}" if resolved_version else " (floating)"
    click.echo(f"added {final_slug}{version_note} → {entry_dir}")
