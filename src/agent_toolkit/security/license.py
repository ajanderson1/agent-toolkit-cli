"""Security review — category 4: license & legal."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit.security.types import CategoryResult, Verdict

_GREEN_KEYWORDS = ("MIT License", "Apache License", "BSD ", "ISC License", "Mozilla Public License")
_AMBER_KEYWORDS = ("All rights reserved", "Proprietary", "Custom License", "GPL", "AGPL")


def scan_license(repo_path: Path) -> CategoryResult:
    candidates = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"]
    license_path: Path | None = None
    for name in candidates:
        candidate = repo_path / name
        if candidate.exists():
            license_path = candidate
            break

    if license_path is None:
        return CategoryResult(
            category="4. License & legal",
            verdict=Verdict.RED,
            evidence="LICENSE file missing at repo root.",
            raw_signals={"license_path": None},
        )

    text = license_path.read_text(encoding="utf-8", errors="replace")
    head = text[:400]
    classification, verdict = _classify(head)

    return CategoryResult(
        category="4. License & legal",
        verdict=verdict,
        evidence=f"{classification}. Source: {license_path.name}.",
        raw_signals={"license_path": str(license_path), "classification": classification},
    )


def _classify(head: str) -> tuple[str, Verdict]:
    for kw in _GREEN_KEYWORDS:
        if kw in head:
            label = kw.split()[0]
            return f"{label}-style permissive license. Compatible with MIT default.", Verdict.GREEN
    for kw in _AMBER_KEYWORDS:
        if kw in head:
            return f"{kw} clause detected — review compatibility manually.", Verdict.AMBER
    return "License present but unclassified by automated check — review manually.", Verdict.AMBER
