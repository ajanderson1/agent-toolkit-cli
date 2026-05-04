"""Ingest stage 2 — RESEARCH (offline-friendly inference helper).

The full RESEARCH stage is skill-led (web fetch + judgement). This helper
consumes a local snapshot of the upstream and emits a deterministic
`Proposal`. The skill calls it, then layers web findings on top.
"""
from __future__ import annotations

import json
from pathlib import Path

from agent_toolkit.ingest.types import Proposal

_ALL_HARNESSES = ["claude", "codex", "opencode", "pi"]


def infer_from_snapshot(
    *,
    snapshot_dir: Path,
    slug: str,
    upstream: str | None,
    origin: str | None = None,
) -> Proposal:
    kind = _infer_kind(snapshot_dir)
    harnesses = _infer_harnesses(snapshot_dir, kind=kind)
    vendor_via = _infer_vendor_via(snapshot_dir, upstream=upstream)
    target_path = _canonical_target_path(kind, slug)
    if origin is None:
        origin = "third-party" if upstream else "first-party"
    return Proposal(
        slug=slug,
        kind=kind,
        origin=origin,
        harnesses=harnesses,
        lifecycle="experimental",
        target_path=target_path,
        vendor_via=vendor_via,
        upstream=upstream,
    )


def _infer_kind(d: Path) -> str:
    if (d / "extension.meta.yaml").exists():
        return "pi-extension"
    if (d / "SKILL.md").exists():
        return "skill"
    if (d / "marketplace.json").exists():
        return "plugin"
    if (d / "mcp.json").exists():
        return "mcp"
    pkg = d / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
        except json.JSONDecodeError:
            data = {}
        kw = [k.lower() for k in (data.get("keywords") or [])]
        if "mcp" in kw or any("mcp" in k for k in kw):
            return "mcp"
        if any("pi-extension" in k or k == "pi" for k in kw):
            return "pi-extension"
    if any(p.suffix == ".meta.yaml" for p in d.iterdir() if p.is_file()):
        return "hook"
    return "skill"


def _infer_harnesses(d: Path, *, kind: str) -> list[str]:
    text_blob = _read_text_blob(d)
    blob_l = text_blob.lower()

    explicit_pi = "pi-extension" in blob_l or "pi-coding-agent" in blob_l or "/.pi/" in blob_l
    explicit_codex = "openai codex" in blob_l or "/.codex/" in blob_l or "codex cli" in blob_l
    explicit_claude = "claude code" in blob_l or "/.claude/" in blob_l or "skill tool" in blob_l
    explicit_opencode = "opencode" in blob_l or "/.config/opencode/" in blob_l

    if explicit_pi and not (explicit_codex or explicit_claude or explicit_opencode):
        return ["pi"]
    if explicit_claude and not (explicit_codex or explicit_pi or explicit_opencode):
        return ["claude"]
    if explicit_codex and not (explicit_claude or explicit_pi or explicit_opencode):
        return ["codex"]
    if explicit_opencode and not (explicit_claude or explicit_pi or explicit_codex):
        return ["opencode"]

    # Default: harness-agnostic skill — all four. For non-skill kinds where only
    # claude has full support today, narrow to claude.
    if kind == "pi-extension":
        return ["pi"]
    if kind == "skill":
        return list(_ALL_HARNESSES)
    if kind in ("agent",):
        return ["claude", "pi"]  # agent kind supported by both
    return ["claude"]


def _infer_vendor_via(d: Path, *, upstream: str | None) -> str:
    if upstream is None:
        return "copy"
    if (d / ".git").exists() or upstream.startswith("https://github.com/"):
        return "submodule"
    return "clone"


def _canonical_target_path(kind: str, slug: str) -> str:
    return {
        "skill": f"skills/{slug}/SKILL.md",
        "agent": f"agents/{slug}.md",
        "command": f"commands/{slug}.md",
        "hook": f"hooks/{slug}.meta.yaml",
        "mcp": f"mcps/{slug}/mcp.json",
        "plugin": f"plugins/{slug}/marketplace.json",
        "pi-extension": f"extensions/{slug}/extension.meta.yaml",
    }[kind]


def _read_text_blob(d: Path) -> str:
    parts: list[str] = []
    for name in ("README.md", "README", "README.txt", "package.json", "SKILL.md"):
        p = d / name
        if p.exists():
            try:
                parts.append(p.read_text(encoding="utf-8", errors="ignore"))
            except Exception:  # noqa: BLE001
                continue
    return "\n".join(parts)
