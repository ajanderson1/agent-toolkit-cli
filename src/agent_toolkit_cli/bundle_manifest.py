"""Parse + validate a toolkit-native bundle manifest (v1).

A bundle is a STATELESS shortcut: a JSON list of asset pointers that
`bundle install` fans out to the per-kind installers. This module is pure
data — it never touches the library, locks, or harness dirs.

`instructions` is NOT a member type (no shareable source). `mcp` is a valid
member type for forward-compat, but the INSTALLER hard-fails on it: the mcp
asset type ships (v4.0.0) but is not yet wired into the bundle installer — that
check lives in bundle_dispatch, not here.

Two parse-time guards (resolved critical-review findings):
- F5: any `source`/`slug`/`ref` value starting with '-' is rejected (an
  option-injection guard — the value is later placed into a CLI argv).
- F6: a `pi-extension` member carrying `ref` is rejected — `pi-extension add`
  has no --ref option, so a pin cannot be honoured and must not be dropped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1

_SOURCE_BACKED_TYPES = frozenset({"skill", "agent", "pi-extension", "mcp"})


class ManifestError(ValueError):
    """A bundle manifest is malformed or invalid."""


@dataclass(frozen=True)
class BundleMember:
    asset_type: str
    source: str
    slug: str | None = None
    ref: str | None = None


@dataclass(frozen=True)
class BundleManifest:
    name: str
    description: str
    members: tuple[BundleMember, ...]


def _parse_member(raw: object, index: int) -> BundleMember:
    if not isinstance(raw, dict):
        raise ManifestError(f"member {index}: must be an object")
    asset_type = raw.get("asset_type")
    if not isinstance(asset_type, str) or not asset_type:
        raise ManifestError(f"member {index}: missing 'asset_type'")
    if asset_type == "instructions":
        raise ManifestError(
            f"member {index}: 'instructions' is not a bundle member type "
            "(it has no shareable source — install it directly with "
            "`instructions install`)"
        )
    if asset_type not in _SOURCE_BACKED_TYPES:
        raise ManifestError(
            f"member {index}: unknown asset_type {asset_type!r} "
            f"(expected one of {sorted(_SOURCE_BACKED_TYPES)})"
        )
    source = raw.get("source")
    if not isinstance(source, str) or not source:
        raise ManifestError(
            f"member {index} ({asset_type}): missing required 'source'"
        )
    slug = raw.get("slug")
    ref = raw.get("ref")
    if slug is not None and not isinstance(slug, str):
        raise ManifestError(f"member {index}: 'slug' must be a string")
    if ref is not None and not isinstance(ref, str):
        raise ManifestError(f"member {index}: 'ref' must be a string")
    if asset_type == "pi-extension" and ref is not None:
        raise ManifestError(
            f"member {index} (pi-extension): pi-extension does not support ref "
            "(its `add` has no --ref option). Remove the 'ref' field."
        )
    for field_name, value in (("source", source), ("slug", slug), ("ref", ref)):
        if isinstance(value, str) and value.startswith("-"):
            raise ManifestError(
                f"member {index}: {field_name!r} must not start with '-' "
                f"(got {value!r}) — rejected as a possible option injection"
            )
    return BundleMember(asset_type=asset_type, source=source, slug=slug, ref=ref)


def parse(data: object) -> BundleManifest:
    """Validate a decoded JSON object into a typed BundleManifest."""
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a JSON object")
    version = data.get("schema_version")
    if version != CURRENT_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported schema_version {version!r} "
            f"(this toolkit supports {CURRENT_SCHEMA_VERSION})"
        )
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise ManifestError("manifest: missing required 'name'")
    description = data.get("description", "")
    if not isinstance(description, str):
        raise ManifestError("manifest: 'description' must be a string")
    members_raw = data.get("members")
    if not isinstance(members_raw, list) or not members_raw:
        raise ManifestError("manifest: 'members' must be a non-empty array")
    members = tuple(_parse_member(m, i) for i, m in enumerate(members_raw))
    return BundleManifest(name=name, description=description, members=members)


def load(path: Path) -> BundleManifest:
    """Read + parse a manifest from a local file path."""
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc
    return parse(data)
