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
    ("mcp", "mcps", "config.json"),
    ("pi-extension", "extensions", "extension.meta.yaml"),
)

# Kinds for which sidecar metadata discovery is supported.
_SIDECAR_KINDS = frozenset({"skill", "mcp"})

# Per-kind root directory (matches _KIND_RULES but indexed for lookup).
_KIND_ROOT = {kind: root_name for kind, root_name, _ in _KIND_RULES}


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

    For most kinds the frontmatter lives in `asset_path` itself. MCPs are the
    exception: discovery triggers on `config.json`, but frontmatter lives in
    the sibling `README.md`.
    """
    if kind == "mcp":
        return asset_path.parent / "README.md"
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
            assets.append(Asset(kind=kind, slug=slug, path=path))
    assets.extend(_discover_plugins(toolkit_root, submodule_paths))
    return sorted(assets, key=lambda a: (a.kind, a.slug))


def _discover_plugins(toolkit_root: Path, submodule_paths: list[Path]) -> list[Asset]:
    """Discover plugins under plugins/<slug>/.claude-plugin/.

    Each .claude-plugin/ directory yields at most one Asset: marketplace.json
    takes precedence over plugin.json (the spec treats them as alternatives).
    """
    plugin_root = toolkit_root / "plugins"
    if not plugin_root.exists():
        return []
    assets: list[Asset] = []
    for claude_dir in sorted(plugin_root.rglob(".claude-plugin")):
        if not claude_dir.is_dir():
            continue
        if _path_is_inside_submodule(claude_dir, toolkit_root, submodule_paths):
            continue
        for filename in _PLUGIN_FILENAMES:
            path = claude_dir / filename
            if path.is_file():
                slug = claude_dir.parent.name
                if slug:
                    assets.append(Asset(kind="plugin", slug=slug, path=path))
                break
    return assets


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


def load_asset_record(asset: Asset) -> AssetRecord:
    """Load full metadata and a body excerpt for an asset."""
    import json as _json

    metadata: dict
    body_excerpt: str = ""

    if asset.kind in {"skill", "agent", "command"}:
        fm_path = frontmatter_path(asset.path, asset.kind)
        text = fm_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        metadata = extract_frontmatter(fm_path) or {}
        body = _strip_frontmatter(text)
        body_excerpt = _first_paragraph(body, max_chars=400)
    elif asset.kind in {"hook", "pi-extension"}:
        metadata = yaml.safe_load(asset.path.read_text()) or {}
    elif asset.kind == "mcp":
        fm_path = frontmatter_path(asset.path, asset.kind)
        if fm_path.is_file():
            text = fm_path.read_text(encoding="utf-8").replace("\r\n", "\n")
            metadata = extract_frontmatter(fm_path) or {}
            body = _strip_frontmatter(text)
            body_excerpt = _first_paragraph(body, max_chars=400)
        else:
            metadata = {}
    elif asset.kind == "plugin":
        doc = _json.loads(asset.path.read_text())
        metadata = doc.get("agent_toolkit_cli") or {}
    else:
        metadata = {}

    requires: dict[str, list[str]] = (metadata.get("spec") or {}).get("requires") or {}

    return AssetRecord(asset=asset, metadata=metadata, body_excerpt=body_excerpt, requires=requires)


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
