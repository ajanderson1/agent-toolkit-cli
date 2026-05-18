"""Render an OverallReport as the human-readable text shown at the GO/NO-GO gate."""
from __future__ import annotations

from agent_toolkit_cli.security.types import OverallReport, Verdict


def render_report(report: OverallReport) -> str:
    lines: list[str] = []
    upstream = report.upstream or "<unknown source>"
    lines.append(f"SECURITY REVIEW — {upstream}")
    lines.append(f"Provenance: {report.provenance}")
    lines.append("")
    for cat in report.categories:
        if cat.skipped:
            label = "[N/A]"
        else:
            label = f"[{cat.verdict.label():<5}]"
        lines.append(f"{label} {cat.category}")
        for line in _wrap(cat.evidence, indent=8):
            lines.append(line)
        lines.append("")
    counts = _vote_counts(report)
    summary = ", ".join(f"{n} {label}" for label, n in counts.items() if n)
    lines.append(f"OVERALL: {report.overall.label()} ({summary})")
    lines.append(f"RECOMMENDATION: {report.recommendation}")
    return "\n".join(lines) + "\n"


def _vote_counts(report: OverallReport) -> dict[str, int]:
    out = {"green": 0, "amber": 0, "red": 0}
    for c in report.categories:
        if c.skipped:
            continue
        out[c.verdict.label().lower()] += 1
    return out


def _wrap(text: str, *, indent: int = 8, width: int = 80) -> list[str]:
    pad = " " * indent
    if not text:
        return [pad + "(no evidence)"]
    out: list[str] = []
    line: list[str] = []
    line_len = 0
    for word in text.split():
        if line_len + len(word) + 1 > width - indent:
            out.append(pad + " ".join(line))
            line, line_len = [word], len(word)
        else:
            line.append(word)
            line_len += len(word) + 1
    if line:
        out.append(pad + " ".join(line))
    return out
