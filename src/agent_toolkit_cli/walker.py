"""Asset directory walker and frontmatter extractor."""
from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONTMATTER_DELIM = "---"

# Filenames that are documentation, not assets, even when they live under
# agents/ or commands/ where the discovery rule is "*.md".
_DOC_FILENAMES = frozenset({"README.md", "CLAUDE.md", "AGENTS.md"})

# Asset kind → (root dir, file pattern, how to find slug from path)
# Discovery walks each kind's root and yields one Asset per match.
_KIND_RULES = (
    ("skill", "skills", "SKILL.md"),
    ("agent", "agents", "*.md"),
    ("command", "commands", "*.md"),
    ("hook", "hooks", "*.meta.yaml"),
    # mcp is now sidecar-only — discovered in the second pass via *.toolkit.yaml
    ("pi-extension", "extensions", "extension.meta.yaml"),
)

# Kinds for which sidecar metadata discovery is supported.
_SIDECAR_KINDS = frozenset({"skill", "mcp"})

# Per-kind root directory (matches _KIND_RULES but indexed for lookup).
# mcp is absent from _KIND_RULES (sidecar-only) but must remain here for the
# second-pass sidecar discovery and _sidecar_path() lookups.
_KIND_ROOT = {kind: root_name for kind, root_name, _ in _KIND_RULES}
_KIND_ROOT["mcp"] = "mcps"


def _sidecar_path(kind: str, slug: str, toolkit_root: Path) -> Path:
    """Return the sidecar path for a given kind + slug.

    Raises ValueError if the kind does not support sidecars.
    """
    if kind not in _SIDECAR_KINDS:
        raise ValueError(
            f"sidecar not supported for kind {kind!r} (only: {sorted(_SIDECAR_KINDS)})"
        )
    return toolkit_root / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"


# Plugin discovery uses a separate two-step walk because the canonical layout
# places either plugin.json or marketplace.json inside a .claude-plugin/
# subdirectory, and we want exactly one Asset per plugin directory regardless
# of which file is present.
_PLUGIN_FILENAMES = ("marketplace.json", "plugin.json")


@dataclass(frozen=True)
class Asset:
    kind: str
    slug: str
    path: Path  # the file carrying the metadata (SKILL.md, mcp.json, *.meta.yaml, etc.)


def frontmatter_path(asset_path: Path, kind: str) -> Path:
    """Return the file carrying the asset's YAML frontmatter.

    Skills and MCPs use sidecar metadata at `<root>/<slug>.toolkit.yaml`.
    All other kinds use inline frontmatter in `asset_path` itself.
    """
    if kind in _SIDECAR_KINDS:
        slug = asset_path.parent.name
        toolkit_root_candidate = asset_path.parent.parent.parent
        sidecar = toolkit_root_candidate / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"
        if sidecar.is_file():
            return sidecar
    return asset_path


def extract_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith(FRONTMATTER_DELIM + "\n"):
        return None
    end = text.find("\n" + FRONTMATTER_DELIM + "\n", len(FRONTMATTER_DELIM) + 1)
    if end == -1:
        return None
    block = text[len(FRONTMATTER_DELIM) + 1 : end]
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def read_sidecar(path: Path) -> dict | None:
    """Read a sidecar YAML file. Returns None if missing, unparseable, or not a dict."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    return parsed if isinstance(parsed, dict) else None


def is_toolkit_frontmatter(metadata: dict | None) -> bool:
    """True iff the parsed frontmatter looks like a toolkit asset descriptor.

    Used to distinguish toolkit-shape frontmatter (apiVersion: agent-toolkit/...)
    from upstream/agentskills.io frontmatter (just name + description).
    """
    if not isinstance(metadata, dict):
        return False
    api = metadata.get("apiVersion")
    return isinstance(api, str) and api.startswith("agent-toolkit/")


def extract_metadata(path: Path) -> dict | None:
    """Read metadata from either an inline-frontmatter file or a bare-YAML sidecar.

    Discriminates by filename: *.toolkit.yaml → bare YAML; everything else →
    inline frontmatter between --- markers.
    """
    if path.name.endswith(".toolkit.yaml"):
        return read_sidecar(path)
    return extract_frontmatter(path)


class BothMetadataLocationsExist(Exception):
    """Raised when both sidecar AND inline frontmatter exist for the same slug."""

    def __init__(self, kind: str, slug: str, sidecar_path: Path, inline_path: Path) -> None:
        self.kind = kind
        self.slug = slug
        self.sidecar_path = sidecar_path
        self.inline_path = inline_path
        super().__init__(
            f"{kind}/{slug}: both {sidecar_path} and {inline_path} exist. Delete one."
        )


def _inline_body_path(kind: str, slug: str, toolkit_root: Path) -> Path:
    """Return the file that carries inline frontmatter for sidecar-supporting kinds."""
    if kind == "skill":
        return toolkit_root / "skills" / slug / "SKILL.md"
    if kind == "mcp":
        return toolkit_root / "mcps" / slug / "README.md"
    raise ValueError(f"inline body path not defined for kind {kind!r}")


def resolve_metadata(
    kind: str,
    slug: str,
    toolkit_root: Path,
) -> tuple[dict | None, Path | None]:
    """Resolve asset metadata for a sidecar-supporting kind.

    Returns (metadata_dict, source_path) on success; (None, None) if neither
    location exists. Raises BothMetadataLocationsExist if both exist.
    """
    if kind not in _SIDECAR_KINDS:
        raise ValueError(f"resolve_metadata called for non-sidecar kind {kind!r}")
    sidecar = _sidecar_path(kind, slug, toolkit_root)
    inline_path = _inline_body_path(kind, slug, toolkit_root)
    sidecar_meta = read_sidecar(sidecar)
    raw_inline_meta = extract_frontmatter(inline_path) if inline_path.is_file() else None
    # Only treat inline frontmatter as toolkit metadata if it has the toolkit
    # apiVersion — upstream-shape frontmatter (name+description only) is not
    # a collision with the sidecar.
    inline_meta = raw_inline_meta if is_toolkit_frontmatter(raw_inline_meta) else None
    if sidecar_meta is not None and inline_meta is not None:
        raise BothMetadataLocationsExist(kind, slug, sidecar, inline_path)
    if sidecar_meta is not None:
        return sidecar_meta, sidecar
    if inline_meta is not None:
        return inline_meta, inline_path
    return None, None


def discover_assets(toolkit_root: Path) -> list[Asset]:
    submodule_paths = _read_submodule_paths(toolkit_root)
    assets: list[Asset] = []
    for kind, root_name, pattern in _KIND_RULES:
        root = toolkit_root / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob(pattern)):
            if kind in {"agent", "command"} and path.name in _DOC_FILENAMES:
                continue
            if _path_is_inside_submodule(path, toolkit_root, submodule_paths):
                continue
            slug = _slug_for(kind, path, root)
            if slug is None:
                continue
            # For sidecar-supporting kinds, skip assets whose metadata lives in
            # a sidecar — the second pass will yield those. This prevents the
            # same Asset from appearing twice (once here, once from the sidecar
            # pass) when the primary file has no inline frontmatter.
            if kind in _SIDECAR_KINDS and _sidecar_path(kind, slug, toolkit_root).is_file():
                continue
            assets.append(Asset(kind=kind, slug=slug, path=path))
    assets.extend(_discover_plugins(toolkit_root, submodule_paths))

    # Second pass: yield sidecar-described skills and mcps. The body directory
    # for each must exist (sidecars without a body are surfaced by `check`,
    # not yielded as Assets here).
    for kind in _SIDECAR_KINDS:
        root_name = _KIND_ROOT[kind]
        root = toolkit_root / root_name
        if not root.exists():
            continue
        for sidecar in sorted(root.glob("*.toolkit.yaml")):
            slug = sidecar.name[: -len(".toolkit.yaml")]
            body_dir = root / slug
            if not body_dir.is_dir():
                # Orphan sidecar — surfaced by check, not yielded as Asset
                continue
            # Determine the asset's primary file (for the Asset.path field —
            # callers use this with frontmatter_path() to find metadata).
            if kind == "skill":
                primary = body_dir / "SKILL.md"
            else:  # mcp
                primary = body_dir / "config.json"
            if not primary.is_file():
                continue
            # Skip if toolkit-shape inline frontmatter ALSO exists at primary —
            # the mutex case. Upstream-shape frontmatter (no apiVersion) is not
            # a conflict; those bodies are exactly the submoduled-skill use case.
            # We don't raise here; check.py raises with a better message.
            # The walker just skips, so duplicate Assets aren't yielded.
            if is_toolkit_frontmatter(extract_frontmatter(primary)):
                continue
            assets.append(Asset(kind=kind, slug=slug, path=primary))

    return sorted(assets, key=lambda a: (a.kind, a.slug))


def _discover_plugins(toolkit_root: Path, submodule_paths: list[Path]) -> list[Asset]:
    """Discover plugin assets.

    Canonical layout: ``plugins/<slug>.toolkit.yaml`` (sidecar-only).
    Legacy layout:    ``plugins/<slug>/.claude-plugin/{plugin,marketplace}.json``
                      with an inline ``agent_toolkit_cli`` block.

    Mutex: if both forms exist for the same slug, raise ``ValueError``.
    """
    plugin_root = toolkit_root / "plugins"
    if not plugin_root.exists():
        return []
    assets: dict[str, Asset] = {}

    # Pass 1: sidecars (canonical).
    for sidecar in sorted(plugin_root.glob("*.toolkit.yaml")):
        if _path_is_inside_submodule(sidecar, toolkit_root, submodule_paths):
            continue
        slug = sidecar.name.removesuffix(".toolkit.yaml")
        if not slug:
            continue
        try:
            doc = yaml.safe_load(sidecar.read_text()) or {}
        except yaml.YAMLError:
            continue
        if (doc.get("metadata") or {}).get("kind") != "plugin":
            continue
        assets[slug] = Asset(kind="plugin", slug=slug, path=sidecar)

    # Pass 2: legacy inline blocks (deprecation fall-back).
    for claude_dir in sorted(plugin_root.rglob(".claude-plugin")):
        if not claude_dir.is_dir():
            continue
        if _path_is_inside_submodule(claude_dir, toolkit_root, submodule_paths):
            continue
        slug = claude_dir.parent.name
        if not slug:
            continue
        for filename in _PLUGIN_FILENAMES:
            path = claude_dir / filename
            if path.is_file():
                if slug in assets:
                    raise ValueError(
                        f"plugin {slug!r}: both sidecar and inline agent_toolkit_cli "
                        f"block present — remove one (see AGENTS.md § Asset identity)"
                    )
                assets[slug] = Asset(kind="plugin", slug=slug, path=path)
                break
    return list(assets.values())


def _read_submodule_paths(toolkit_root: Path) -> list[Path]:
    gm = toolkit_root / ".gitmodules"
    if not gm.exists():
        return []
    parser = configparser.ConfigParser()
    parser.read(gm)
    paths: list[Path] = []
    for sect in parser.sections():
        rel = parser[sect].get("path")
        if rel:
            paths.append((toolkit_root / rel).resolve())
    return paths


def _path_is_inside_submodule(path: Path, toolkit_root: Path, submodule_paths: list[Path]) -> bool:
    resolved = path.resolve()
    for sm in submodule_paths:
        try:
            resolved.relative_to(sm)
            return True
        except ValueError:
            continue
    return False


def _slug_for(kind: str, path: Path, root: Path) -> str | None:
    if kind == "hook":
        # Subdirectory layout: hooks/<slug>/.meta.yaml → "<slug>" (from parent dir).
        # Flat layout: hooks/confirm-rm.meta.yaml → "confirm-rm" (from filename).
        if path.name == ".meta.yaml":
            return path.parent.name or None
        return path.name.removesuffix(".meta.yaml") or None
    if kind in {"skill", "mcp", "pi-extension"}:
        # skills/<...>/<slug>/SKILL.md → "<slug>" (last directory component)
        return path.parent.name or None
    if kind in {"agent", "command"}:
        # agents/<...>/<slug>.md → "<slug>"
        return path.stem or None
    return None


@dataclass(frozen=True)
class AssetRecord:
    asset: Asset
    metadata: dict
    body_excerpt: str  # first paragraph or first 400 chars, whichever is shorter; "" if no body
    requires: dict[str, list[str]]  # harness → list of "kind:slug" strings; {} if absent
    harness_description: str | None = None  # SKILL.md top-level `description`; None for non-skills
    cli_description: str | None = None      # sidecar `metadata.description`; None for non-skills


def load_asset_record(asset: Asset) -> AssetRecord:
    """Load full metadata and a body excerpt for an asset."""
    import json as _json

    metadata: dict
    body_excerpt: str = ""
    harness_description: str | None = None
    cli_description: str | None = None

    if asset.kind == "skill":
        toolkit_root = asset.path.parent.parent.parent
        sidecar = _sidecar_path("skill", asset.slug, toolkit_root)
        skill_md_fm = extract_metadata(asset.path) or {}
        if sidecar.is_file():
            # New shape: sidecar carries v1alpha2 metadata; SKILL.md has its own frontmatter.
            metadata = read_sidecar(sidecar) or {}
            harness_description = skill_md_fm.get("description")
            cli_description = (metadata.get("metadata") or {}).get("description")
            # Body: asset.path (SKILL.md) has non-toolkit frontmatter; read it and strip.
            text = asset.path.read_text(encoding="utf-8").replace("\r\n", "\n")
            body = _strip_frontmatter(text)
        else:
            # Legacy inline shape: all metadata is in SKILL.md frontmatter.
            metadata = skill_md_fm
            legacy_desc = (metadata.get("metadata") or {}).get("description")
            harness_description = legacy_desc
            cli_description = legacy_desc
            text = asset.path.read_text(encoding="utf-8").replace("\r\n", "\n")
            body = _strip_frontmatter(text)
        body_excerpt = _first_paragraph(body, max_chars=400)
    elif asset.kind in {"agent", "command"}:
        fm_path = frontmatter_path(asset.path, asset.kind)
        metadata = extract_metadata(fm_path) or {}
        # Body excerpt comes from the asset's primary file, not the sidecar.
        # When metadata lives in a sidecar, the body file has no frontmatter
        # to strip — so we read the body file directly.
        if fm_path != asset.path:
            # Sidecar case: read body from asset.path (the primary file)
            body = asset.path.read_text(encoding="utf-8").replace("\r\n", "\n")
        else:
            # Inline-frontmatter case: strip frontmatter from the same file
            text = fm_path.read_text(encoding="utf-8").replace("\r\n", "\n")
            body = _strip_frontmatter(text)
        body_excerpt = _first_paragraph(body, max_chars=400)
    elif asset.kind in {"hook", "pi-extension"}:
        metadata = yaml.safe_load(asset.path.read_text()) or {}
    elif asset.kind == "mcp":
        fm_path = frontmatter_path(asset.path, asset.kind)
        # MCPs are sidecar-only; fm_path is always a *.toolkit.yaml path.
        # body_excerpt stays "" (the body is config.json/code, not prose).
        metadata = (extract_metadata(fm_path) if fm_path.is_file() else None) or {}
    elif asset.kind == "plugin":
        if asset.path.name.endswith(".toolkit.yaml"):
            metadata = yaml.safe_load(asset.path.read_text()) or {}
        else:
            doc = _json.loads(asset.path.read_text())
            metadata = doc.get("agent_toolkit_cli") or {}
    else:
        metadata = {}

    requires: dict[str, list[str]] = (metadata.get("spec") or {}).get("requires") or {}

    return AssetRecord(
        asset=asset,
        metadata=metadata,
        body_excerpt=body_excerpt,
        requires=requires,
        harness_description=harness_description,
        cli_description=cli_description,
    )


def strip_frontmatter(text: str) -> str:
    """Public alias for `_strip_frontmatter` — return the markdown body
    of a frontmatter-bearing document (or the whole text if no frontmatter).
    """
    return _strip_frontmatter(text)


def _strip_frontmatter(text: str) -> str:
    if not text.startswith(FRONTMATTER_DELIM + "\n"):
        return text
    end = text.find("\n" + FRONTMATTER_DELIM + "\n", len(FRONTMATTER_DELIM) + 1)
    if end == -1:
        return text
    return text[end + len(FRONTMATTER_DELIM) + 2 :]


_HEADING_RE = re.compile(r"^#{1,6}(\s|$)")


def _first_paragraph(body: str, max_chars: int) -> str:
    body = body.lstrip()
    # Skip ATX heading lines at the top. An ATX heading requires whitespace
    # (or end-of-line) after the '#'s — so a body line like "#1 priority"
    # is body, not a heading.
    while body and _HEADING_RE.match(body):
        nl = body.find("\n")
        if nl == -1:
            return ""
        body = body[nl + 1 :].lstrip()
    para_end = body.find("\n\n")
    para = body if para_end == -1 else body[:para_end]
    para = para.strip()
    if len(para) > max_chars:
        return para[:max_chars].rstrip()
    return para
