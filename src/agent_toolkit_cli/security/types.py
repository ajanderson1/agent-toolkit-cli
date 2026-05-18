"""Type definitions for security review."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Verdict(IntEnum):
    GREEN = 0
    AMBER = 1
    RED = 2

    def label(self) -> str:
        return {Verdict.GREEN: "GREEN", Verdict.AMBER: "AMBER", Verdict.RED: "RED"}[self]


@dataclass
class CategoryResult:
    category: str
    verdict: Verdict
    evidence: str  # one paragraph
    raw_signals: dict = field(default_factory=dict)
    skipped: bool = False  # True if marked [N/A] (file-input case)


@dataclass
class OverallReport:
    provenance: str
    upstream: str | None
    categories: list[CategoryResult]
    overall: Verdict
    recommendation: str  # "Recommend GO" / "GO with caveats: …" / "Recommend NO-GO"

    @classmethod
    def compute(
        cls,
        *,
        categories: list[CategoryResult],
        provenance: str,
        upstream: str | None = None,
        recommendation: str = "",
    ) -> "OverallReport":
        active = [c for c in categories if not c.skipped]
        worst = max((c.verdict for c in active), default=Verdict.GREEN)
        amber_count = sum(1 for c in active if c.verdict == Verdict.AMBER)
        if worst == Verdict.RED:
            overall = Verdict.RED
        elif amber_count >= 2:
            overall = Verdict.AMBER
        elif amber_count == 1:
            overall = Verdict.AMBER
        else:
            overall = Verdict.GREEN
        return cls(
            provenance=provenance,
            upstream=upstream,
            categories=categories,
            overall=overall,
            recommendation=recommendation or _default_recommendation(overall),
        )


def _default_recommendation(overall: Verdict) -> str:
    return {
        Verdict.GREEN: "Recommend GO — no blocking issues identified.",
        Verdict.AMBER: "GO with caveats — review amber findings before proceeding.",
        Verdict.RED: "Recommend NO-GO — at least one category is red.",
    }[overall]
