"""Authoritative global inventory for MCP library authoring specifications.

``mcps-library.json`` records expected library state. The config/sidecar pair
under ``~/.agent-toolkit/mcps`` is a materialisation of each manifest record,
not a second source of truth.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlsplit

from agent_toolkit_cli.mcp_adapters import atomic_write_text

if TYPE_CHECKING:
    from agent_toolkit_cli.mcp_library import McpAsset

MANIFEST_FILENAME = "mcps-library.json"
MANIFEST_VERSION = 1

_ENTRY_FIELDS = (
    "slug",
    "install_method",
    "transport",
    "source",
    "command",
    "args",
    "env",
    "description",
    "resolved_version",
)
_ENTRY_FIELD_SET = frozenset(_ENTRY_FIELDS)
_METADATA_FIELDS = frozenset(
    {
        "name",
        "install_method",
        "transport",
        "resolved_version",
        "source_dir",
        "env",
        "description",
    }
)
_SUPPORTED_METHODS = frozenset({"npx", "uvx", "docker", "url", "local"})
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REFERENCE_RE = re.compile(r"^\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})$")
_SECRET_NAME_RE = re.compile(
    r"(?:^|[_-])(?:api[_-]?key|token|secret|password|passwd|credential|"
    r"private[_-]?key|access[_-]?key|client[_-]?secret|auth|dsn|database[_-]?url)"
    r"(?:$|[_-])",
    re.IGNORECASE,
)
_PROVIDER_TOKEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"(?:hf_|npm_|glpat-)[A-Za-z0-9_-]{20,}"),
)
_BEARER_RE = re.compile(r"\bbearer\s+([^\s,;]+)", re.IGNORECASE)
_ASSIGNMENT_RE = re.compile(
    r"^(?:--?)?([A-Za-z_][A-Za-z0-9_-]*)=(.*)$",
    re.DOTALL,
)
_OPTION_RE = re.compile(r"^--?([A-Za-z_][A-Za-z0-9_-]*)$")


@dataclass(frozen=True)
class McpManifestEntry:
    """Complete authoring specification for one MCP library entry."""

    slug: str
    install_method: str
    transport: str
    source: str
    command: str | None
    args: tuple[str, ...]
    env: tuple[str, ...]
    description: str | None
    resolved_version: str | None


class UnsafeMcpSpecError(ValueError):
    """An MCP authoring field contains a likely literal secret.

    The message deliberately carries only a field path and never the value.
    """

    def __init__(self, field_path: str) -> None:
        super().__init__(f"unsafe literal at {field_path}; value redacted")
        self.field_path = field_path


def manifest_path(home: Path) -> Path:
    """Return the global MCP library manifest path for ``home``."""
    return home / ".agent-toolkit" / MANIFEST_FILENAME


def read_manifest(path: Path) -> dict[str, McpManifestEntry]:
    """Read and strictly validate a v1 manifest; a missing path is empty."""
    if not path.is_file():
        return {}

    raw = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_object_without_duplicates
    )
    if (
        not isinstance(raw, dict)
        or set(raw) != {"version", "mcps"}
        or type(raw.get("version")) is not int
        or raw.get("version") != MANIFEST_VERSION
        or not isinstance(raw.get("mcps"), dict)
    ):
        raise ValueError(f"{path}: unsupported or malformed MCP library manifest")

    entries: dict[str, McpManifestEntry] = {}
    for key, value in raw["mcps"].items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise ValueError(f"{path}: malformed MCP library manifest entry")
        entry = _entry_from_raw(value, path=path)
        if entry.slug != key:
            raise ValueError(f"{path}: MCP manifest slug does not match its map key")
        entries[key] = entry
    return entries


def write_manifest(path: Path, entries: dict[str, McpManifestEntry]) -> None:
    """Strictly validate and atomically replace a sorted v1 manifest."""
    serialised: dict[str, dict[str, object]] = {}
    for slug in sorted(entries):
        entry = entries[slug]
        if not isinstance(slug, str) or not isinstance(entry, McpManifestEntry):
            raise ValueError("malformed MCP library manifest entry")
        if slug != entry.slug:
            raise ValueError("MCP manifest slug does not match its map key")
        _validate_entry(entry)
        assert_safe_entry(entry)
        serialised[slug] = _entry_to_raw(entry)

    body = {"version": MANIFEST_VERSION, "mcps": serialised}
    atomic_write_text(path, json.dumps(body, indent=2) + "\n")


def entry_to_inner_config(entry: McpManifestEntry) -> dict[str, object]:
    """Derive the harness-neutral config materialisation from an entry."""
    _validate_entry(entry)
    assert_safe_entry(entry)
    if entry.install_method == "url":
        return {"type": "http", "url": entry.source}
    return {
        "type": "stdio",
        "command": entry.command,
        "args": list(entry.args),
    }


def entry_to_metadata(entry: McpManifestEntry) -> dict[str, object]:
    """Derive the deterministic sidecar materialisation from an entry."""
    _validate_entry(entry)
    assert_safe_entry(entry)
    metadata: dict[str, object] = {
        "name": entry.slug,
        "install_method": entry.install_method,
        "transport": entry.transport,
    }
    if entry.resolved_version is not None:
        metadata["resolved_version"] = entry.resolved_version
    if entry.install_method == "local":
        metadata["source_dir"] = entry.source
    if entry.env:
        metadata["env"] = list(entry.env)
    if entry.description is not None:
        metadata["description"] = entry.description
    return metadata


def entry_from_materialisation(asset: McpAsset) -> McpManifestEntry:
    """Losslessly reconstruct an entry from a legacy config/sidecar pair.

    Unknown fields and config-level ``env`` maps are rejected rather than
    guessed or discarded. Errors never include source values.
    """
    inner = asset.inner_config
    metadata = asset.metadata
    if not isinstance(inner, dict) or not isinstance(metadata, dict):
        raise ValueError("MCP materialisation cannot be reconstructed losslessly")

    _assert_safe_materialisation(inner, metadata)
    if "env" in inner:
        raise ValueError(
            "MCP materialisation env map cannot be reconstructed losslessly; "
            "value redacted"
        )
    if not set(metadata).issubset(_METADATA_FIELDS):
        raise ValueError("MCP materialisation cannot be reconstructed losslessly")
    if not {"name", "install_method", "transport"}.issubset(metadata):
        raise ValueError("MCP materialisation cannot be reconstructed losslessly")
    if metadata["name"] != asset.slug:
        raise ValueError("MCP materialisation name does not match its slug")

    method = metadata["install_method"]
    transport = metadata["transport"]
    description = metadata.get("description")
    resolved_version = metadata.get("resolved_version")
    env = metadata.get("env", [])
    if (
        not isinstance(method, str)
        or not isinstance(transport, str)
        or (description is not None and not isinstance(description, str))
        or (resolved_version is not None and not isinstance(resolved_version, str))
        or not isinstance(env, list)
        or not all(isinstance(name, str) for name in env)
    ):
        raise ValueError("MCP materialisation cannot be reconstructed losslessly")

    source: str
    command: str | None
    args: tuple[str, ...]
    if method == "url":
        if set(inner) != {"type", "url"} or inner.get("type") != "http":
            raise ValueError("MCP materialisation cannot be reconstructed losslessly")
        source_value = inner.get("url")
        if not isinstance(source_value, str):
            raise ValueError("MCP materialisation cannot be reconstructed losslessly")
        source = source_value
        command = None
        args = ()
    else:
        if set(inner) != {"type", "command", "args"} or inner.get("type") != "stdio":
            raise ValueError("MCP materialisation cannot be reconstructed losslessly")
        command_value = inner.get("command")
        args_value = inner.get("args")
        if (
            not isinstance(command_value, str)
            or not isinstance(args_value, list)
            or not all(isinstance(arg, str) for arg in args_value)
            or not args_value
        ):
            raise ValueError("MCP materialisation cannot be reconstructed losslessly")
        command = command_value
        args = tuple(args_value)
        if method == "npx":
            source = _npx_source(args[-1])
        elif method == "uvx":
            source = args[-1].split("==", 1)[0]
        elif method == "docker":
            source = args[-1]
        elif method == "local":
            source_value = metadata.get("source_dir")
            if not isinstance(source_value, str):
                raise ValueError("MCP materialisation cannot be reconstructed losslessly")
            source = source_value
        else:
            raise ValueError("MCP materialisation cannot be reconstructed losslessly")

    entry = McpManifestEntry(
        slug=asset.slug,
        install_method=method,
        transport=transport,
        source=source,
        command=command,
        args=args,
        env=tuple(env),
        description=description,
        resolved_version=resolved_version,
    )
    _validate_entry(entry)
    assert_safe_entry(entry)
    return entry


def assert_safe_entry(entry: McpManifestEntry) -> None:
    """Reject likely literal secrets without retaining them in the error."""
    _validate_entry_types(entry)
    _assert_safe_string("source", entry.source, inspect_url=True)
    if entry.command is not None:
        _assert_safe_string("command", entry.command, inspect_url=True)
    _assert_safe_args(entry.args)
    if entry.description is not None:
        _assert_safe_string("description", entry.description, inspect_url=True)


def _entry_from_raw(raw: dict[str, Any], *, path: Path) -> McpManifestEntry:
    if set(raw) != _ENTRY_FIELD_SET:
        raise ValueError(f"{path}: malformed MCP library manifest entry")
    args = raw.get("args")
    env = raw.get("env")
    if not isinstance(args, list) or not isinstance(env, list):
        raise ValueError(f"{path}: malformed MCP library manifest entry")
    entry = McpManifestEntry(
        slug=raw.get("slug"),
        install_method=raw.get("install_method"),
        transport=raw.get("transport"),
        source=raw.get("source"),
        command=raw.get("command"),
        args=tuple(args),
        env=tuple(env),
        description=raw.get("description"),
        resolved_version=raw.get("resolved_version"),
    )
    try:
        _validate_entry(entry)
        assert_safe_entry(entry)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, UnsafeMcpSpecError):
            raise
        raise ValueError(f"{path}: malformed MCP library manifest entry") from None
    return entry


def _entry_to_raw(entry: McpManifestEntry) -> dict[str, object]:
    return {
        "slug": entry.slug,
        "install_method": entry.install_method,
        "transport": entry.transport,
        "source": entry.source,
        "command": entry.command,
        "args": list(entry.args),
        "env": list(entry.env),
        "description": entry.description,
        "resolved_version": entry.resolved_version,
    }


def _validate_entry_types(entry: McpManifestEntry) -> None:
    if (
        not isinstance(entry.slug, str)
        or not isinstance(entry.install_method, str)
        or not isinstance(entry.transport, str)
        or not isinstance(entry.source, str)
        or (entry.command is not None and not isinstance(entry.command, str))
        or not isinstance(entry.args, tuple)
        or not all(isinstance(arg, str) for arg in entry.args)
        or not isinstance(entry.env, tuple)
        or not all(isinstance(name, str) for name in entry.env)
        or (entry.description is not None and not isinstance(entry.description, str))
        or (
            entry.resolved_version is not None
            and not isinstance(entry.resolved_version, str)
        )
    ):
        raise ValueError("malformed MCP library manifest entry")


def _validate_entry(entry: McpManifestEntry) -> None:
    _validate_entry_types(entry)
    if (
        not _SLUG_RE.fullmatch(entry.slug)
        or entry.slug in {".", ".."}
        or entry.install_method not in _SUPPORTED_METHODS
        or not entry.source
        or len(set(entry.env)) != len(entry.env)
        or any(not _ENV_NAME_RE.fullmatch(name) for name in entry.env)
    ):
        raise ValueError("malformed MCP library manifest entry")

    if entry.install_method == "url":
        parsed = urlsplit(entry.source)
        if (
            entry.transport != "http"
            or entry.command is not None
            or entry.args
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
        ):
            raise ValueError("malformed MCP library manifest entry")
        return

    if entry.transport != "stdio" or not entry.command or not entry.args:
        raise ValueError("malformed MCP library manifest entry")
    if entry.install_method == "npx" and (
        entry.command != "npx" or _npx_source(entry.args[-1]) != entry.source
    ):
        raise ValueError("malformed MCP library manifest entry")
    if entry.install_method == "uvx" and (
        entry.command != "uvx" or entry.args[-1].split("==", 1)[0] != entry.source
    ):
        raise ValueError("malformed MCP library manifest entry")
    if entry.install_method == "docker" and (
        entry.command != "docker" or entry.args[-1] != entry.source
    ):
        raise ValueError("malformed MCP library manifest entry")
    if entry.install_method == "local" and not Path(entry.source).is_absolute():
        raise ValueError("malformed MCP library manifest entry")


def _npx_source(spec: str) -> str:
    if spec.startswith("@"):
        package, separator, _version = spec.rpartition("@")
        return package if separator and package else spec
    return spec.split("@", 1)[0]


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key in MCP library manifest")
        result[key] = value
    return result


def _is_reference(value: str) -> bool:
    return bool(_REFERENCE_RE.fullmatch(value.strip()))


def _is_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME_RE.search(name))


def _assert_safe_string(field_path: str, value: str, *, inspect_url: bool) -> None:
    for pattern in _PROVIDER_TOKEN_PATTERNS:
        if pattern.search(value):
            raise UnsafeMcpSpecError(field_path)

    bearer = _BEARER_RE.search(value)
    if bearer and not _is_reference(bearer.group(1)):
        raise UnsafeMcpSpecError(field_path)

    assignment = _ASSIGNMENT_RE.fullmatch(value)
    if assignment and _is_secret_name(assignment.group(1)):
        assigned = assignment.group(2)
        if assigned and not _is_reference(assigned):
            raise UnsafeMcpSpecError(field_path)

    if not inspect_url:
        return
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise UnsafeMcpSpecError(field_path) from None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeMcpSpecError(field_path)
    for name, query_value in parse_qsl(parsed.query, keep_blank_values=True):
        if _is_secret_name(name) and query_value and not _is_reference(query_value):
            raise UnsafeMcpSpecError(f"{field_path}.query")


def _assert_safe_args(args: tuple[str, ...]) -> None:
    for index, arg in enumerate(args):
        field_path = f"args[{index}]"
        _assert_safe_string(field_path, arg, inspect_url=True)
        option = _OPTION_RE.fullmatch(arg)
        if not option or not _is_secret_name(option.group(1)) or index + 1 >= len(args):
            continue
        value = args[index + 1]
        if value and not value.startswith("-") and not _is_reference(value):
            raise UnsafeMcpSpecError(f"args[{index + 1}]")


def _assert_safe_materialisation(inner: dict, metadata: dict) -> None:
    command = inner.get("command")
    if isinstance(command, str):
        _assert_safe_string("command", command, inspect_url=True)
    args = inner.get("args")
    if isinstance(args, list) and all(isinstance(arg, str) for arg in args):
        _assert_safe_args(tuple(args))
    url = inner.get("url")
    if isinstance(url, str):
        _assert_safe_string("url", url, inspect_url=True)
    env = inner.get("env")
    if isinstance(env, dict):
        for name, value in env.items():
            if (
                isinstance(name, str)
                and isinstance(value, str)
                and _is_secret_name(name)
                and value
                and not _is_reference(value)
            ):
                raise UnsafeMcpSpecError("env")
    description = metadata.get("description")
    if isinstance(description, str):
        _assert_safe_string("description", description, inspect_url=True)
