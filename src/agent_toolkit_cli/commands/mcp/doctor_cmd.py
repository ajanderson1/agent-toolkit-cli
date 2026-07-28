"""`mcp doctor [-g/-p]` — read-only library and projection diagnosis."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import click
import yaml  # type: ignore[import-untyped]

from agent_toolkit_cli.commands.mcp._common import scope_and_roots, scope_banner
from agent_toolkit_cli.mcp_adapters import get_adapter
from agent_toolkit_cli.mcp_library import (
    McpAsset,
    library_root,
    load_mcp_asset,
    scan_entry_files,
)
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock
from agent_toolkit_cli.mcp_manifest import (
    McpManifestEntry,
    UnsafeMcpSpecError,
    entry_from_materialisation,
    entry_to_inner_config,
    entry_to_metadata,
    manifest_path,
    read_manifest,
)
from agent_toolkit_cli.mcp_standard import mcp_standard_covered


@dataclass
class Finding:
    slug: str
    harness: str
    finding_type: str
    detail: str


def _rendered_entry(harness: str, inner_config: dict) -> dict | None:
    """Return the harness-native entry an adapter would write, without writing."""
    from agent_toolkit_cli._install_core import InstallError

    if harness == "codex":
        from agent_toolkit_cli.mcp_adapters.toml_config import _CodexAdapter

        try:
            return _CodexAdapter()._translate(inner_config)
        except InstallError:
            return None
    from agent_toolkit_cli.mcp_adapters.json_config import CELLS

    cell = CELLS.get(harness)
    if cell is None:
        return None
    try:
        return cell.translate(inner_config)
    except InstallError:
        return None


def _installed_entry(
    harness: str,
    slug: str,
    scope: str,
    home: Path,
    project: Path | None,
) -> dict | None:
    """Read one live installed entry, parsed, or return None when absent."""
    adapter = get_adapter(harness)
    try:
        target = adapter.config_target(scope=scope, home=home, project=project)
    except ValueError:
        return None
    if not target.is_file():
        return None
    text = target.read_text(encoding="utf-8")
    if harness == "codex":
        import tomlkit

        try:
            doc = tomlkit.parse(text)
        except Exception:
            return None
        servers = doc.get("mcp_servers")
        if servers is None or slug not in servers:
            return None
        return json.loads(json.dumps(servers[slug]))
    try:
        doc = json.loads(text or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(doc, dict):
        return None
    key = "mcp" if harness == "opencode" else "mcpServers"
    servers = doc.get(key)
    if not isinstance(servers, dict) or slug not in servers:
        return None
    return servers[slug]


def _read_materialisation(
    library: Path, slug: str
) -> tuple[McpManifestEntry | None, str | None]:
    """Reconstruct one pair, returning only redacted failure details."""
    try:
        asset = load_mcp_asset(library, slug)
        return entry_from_materialisation(asset), None
    except UnsafeMcpSpecError as exc:
        return None, f"unsafe literal at {exc.field_path}; value redacted"
    except (OSError, ValueError, yaml.YAMLError):
        return None, "materialisation cannot be reconstructed; value redacted"


def _diagnose_library(
    home: Path,
) -> tuple[list[Finding], bool, dict[str, McpManifestEntry] | None]:
    """Return library findings, missing-manifest remediation, and authority."""
    library = library_root(home)
    physical = scan_entry_files(library)
    path = manifest_path(home)
    manifest_missing = not path.is_file()
    manifest = None if manifest_missing else read_manifest(path)
    findings: list[Finding] = []

    slugs = sorted(set(physical) | (set(manifest) if manifest is not None else set()))
    for slug in slugs:
        config_path, sidecar_path = physical.get(slug, (None, None))
        has_config = config_path is not None
        has_sidecar = sidecar_path is not None
        in_manifest = manifest is not None and slug in manifest

        # Highest-signal precedence is intentional and one-finding-per-slug.
        if has_config != has_sidecar:
            findings.append(
                Finding(
                    slug,
                    "library",
                    "library-entry-half-written",
                    "exactly one of config.json and sidecar exists",
                )
            )
            continue
        if in_manifest and not has_config and not has_sidecar:
            findings.append(
                Finding(
                    slug,
                    "library",
                    "library-entry-missing",
                    "manifest record has no materialisation files",
                )
            )
            continue
        if not in_manifest and has_config and has_sidecar:
            _actual, error = _read_materialisation(library, slug)
            findings.append(
                Finding(
                    slug,
                    "library",
                    "library-entry-orphan",
                    error or "complete materialisation has no manifest record",
                )
            )
            continue
        if in_manifest and has_config and has_sidecar:
            actual, error = _read_materialisation(library, slug)
            if error is not None or actual != manifest[slug]:
                findings.append(
                    Finding(
                        slug,
                        "library",
                        "library-entry-drift",
                        error or "materialisation differs from manifest",
                    )
                )

    return findings, manifest_missing, manifest


def _asset_from_authority(
    slug: str,
    *,
    manifest: dict[str, McpManifestEntry] | None,
    library: Path,
) -> McpAsset | None:
    if manifest is None:
        try:
            return load_mcp_asset(library, slug)
        except (FileNotFoundError, ValueError, yaml.YAMLError):
            return None
    entry = manifest.get(slug)
    if entry is None:
        return None
    return McpAsset(
        slug=slug,
        inner_config=entry_to_inner_config(entry),
        metadata=entry_to_metadata(entry),
    )


def _diagnose(
    *, scope: str, home: Path, project: Path | None
) -> tuple[list[Finding], list[str], bool]:
    """Return findings, name-only env warnings, and migration remediation."""
    library_findings, remediation, manifest = _diagnose_library(home)
    findings = list(library_findings)
    env_warnings: list[str] = []
    library = library_root(home)
    lock = read_lock(lock_path_for_scope(scope, home=home, project=project))
    env_checked: set[str] = set()

    for slug in sorted(lock):
        entries = lock[slug]
        if scope == "project":
            row_harnesses = {entry.harness for entry in entries}
            if row_harnesses & mcp_standard_covered("project"):
                findings.append(
                    Finding(
                        slug=slug,
                        harness="standard",
                        finding_type="legacy-standard-dedup",
                        detail=(
                            "project lock has claude-code/pi rows for the shared "
                            f".mcp.json; collapse to one `standard` row with "
                            f"`mcp install {slug} -p`"
                        ),
                    )
                )

        asset = _asset_from_authority(slug, manifest=manifest, library=library)
        if asset is not None and slug not in env_checked:
            env_checked.add(slug)
            for variable in asset.env:
                if variable not in os.environ:
                    env_warnings.append(
                        f"env var {variable} (declared by {slug}) is not set"
                    )

        for lock_entry in sorted(entries, key=lambda item: item.harness):
            harness = lock_entry.harness
            if harness == "standard" and scope != "project":
                continue
            adapter = get_adapter(harness)
            try:
                installed = adapter.is_installed(
                    slug, scope=scope, home=home, project=project
                )
            except ValueError:
                installed = False
            if not installed:
                findings.append(
                    Finding(
                        slug,
                        harness,
                        "missing",
                        "lock entry exists but no live projection in the harness config",
                    )
                )
                continue
            if asset is None:
                findings.append(
                    Finding(
                        slug,
                        harness,
                        "orphan-library",
                        "projected + locked but the manifest entry is absent/unreadable",
                    )
                )
                continue
            rendered = _rendered_entry(harness, asset.inner_config)
            installed = _installed_entry(harness, slug, scope, home, project)
            if rendered is None or installed is None:
                continue
            if _normalise(rendered) != _normalise(installed):
                findings.append(
                    Finding(
                        slug,
                        harness,
                        "drifted",
                        "installed entry differs structurally from library authority",
                    )
                )

    return findings, env_warnings, remediation


def _normalise(value: object) -> object:
    """Strip ordering and tomlkit artifacts for structural comparison."""
    return json.loads(json.dumps(value, sort_keys=True))


@click.command("doctor")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def doctor_cmd(
    ctx: click.Context,
    global_: bool,
    project_flag: bool,
) -> None:
    """Diagnose MCP library and projection drift without writing."""
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    effective_home = home if home is not None else Path.home()
    lock_path = lock_path_for_scope(scope, home=effective_home, project=project_root)
    scope_banner(
        scope,
        implicit=implicit,
        lock_path=lock_path,
        count=len(read_lock(lock_path)),
    )
    try:
        findings, env_warnings, remediation = _diagnose(
            scope=scope, home=effective_home, project=project_root
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    for warning in env_warnings:
        click.echo(f"WARNING: {warning}")

    if not findings and not remediation:
        if env_warnings:
            click.echo(f"no projection drift ({len(env_warnings)} env warning(s))")
        else:
            click.echo("all clean")
        return

    for finding in findings:
        locus = "global library" if finding.harness == "library" else scope
        click.echo(
            f"{finding.slug} · {finding.harness} · "
            f"{finding.finding_type} ({locus})"
        )
        click.echo(f"  detail: {finding.detail}")

    if remediation:
        click.echo("remediation: agent-toolkit-cli mcp migrate")
    click.echo("")
    click.echo(
        f"summary: {len(findings)} finding(s), "
        f"{len(env_warnings)} env warning(s)"
    )
    ctx.exit(1)
