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
    ("mcp", "mcps", "mcp.json"),
    ("plugin", "plugins", "marketplace.json"),
)


@dataclass(frozen=True)
class Asset:
    kind: str
    slug: str
    path: Path  # the file carrying the metadata (SKILL.md, mcp.json, *.meta.yaml, etc.)


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


def discover_assets(repo_root: Path) -> list[Asset]:
    submodule_paths = _read_submodule_paths(repo_root)
    assets: list[Asset] = []
    for kind, root_name, pattern in _KIND_RULES:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob(pattern)):
            if kind in {"agent", "command"} and path.name in _DOC_FILENAMES:
                continue
            if _path_is_inside_submodule(path, repo_root, submodule_paths):
                continue
            slug = _slug_for(kind, path, root)
            if slug is None:
                continue
            assets.append(Asset(kind=kind, slug=slug, path=path))
    return sorted(assets, key=lambda a: (a.kind, a.slug))


def _read_submodule_paths(repo_root: Path) -> list[Path]:
    gm = repo_root / ".gitmodules"
    if not gm.exists():
        return []
    parser = configparser.ConfigParser()
    parser.read(gm)
    paths: list[Path] = []
    for sect in parser.sections():
        rel = parser[sect].get("path")
        if rel:
            paths.append((repo_root / rel).resolve())
    return paths


def _path_is_inside_submodule(path: Path, repo_root: Path, submodule_paths: list[Path]) -> bool:
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
        # hooks/confirm-rm.meta.yaml → "confirm-rm"
        return path.name.removesuffix(".meta.yaml") or None
    if kind in {"skill", "mcp", "plugin"}:
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


def load_asset_record(asset: Asset) -> AssetRecord:
    """Load full metadata and a body excerpt for an asset."""
    import json as _json

    metadata: dict
    body_excerpt: str = ""

    if asset.kind in {"skill", "agent", "command"}:
        text = asset.path.read_text(encoding="utf-8").replace("\r\n", "\n")
        metadata = extract_frontmatter(asset.path) or {}
        body = _strip_frontmatter(text)
        body_excerpt = _first_paragraph(body, max_chars=400)
    elif asset.kind == "hook":
        metadata = yaml.safe_load(asset.path.read_text()) or {}
    elif asset.kind in {"mcp", "plugin"}:
        doc = _json.loads(asset.path.read_text())
        metadata = doc.get("agent_toolkit") or {}
    else:
        metadata = {}

    return AssetRecord(asset=asset, metadata=metadata, body_excerpt=body_excerpt)


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
