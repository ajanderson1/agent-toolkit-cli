"""Shared, compact presentation primitives for read-only TUI info panes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rich.markup import escape


@dataclass(frozen=True)
class InfoSection:
    """One deliberately small, labelled group in an information pane."""

    title: str
    lines: tuple[str, ...]
    variant: str = "text"


@dataclass(frozen=True)
class InfoFact:
    """A dynamic labelled value that must remain whole until it is escaped."""

    label: str
    value: str

    def __str__(self) -> str:
        return f"{self.label}: {self.value}"


def facts(*items: tuple[str, str]) -> tuple[str, ...]:
    """Render aligned fact labels without making values a prose paragraph."""

    width = max((len(label) for label, _ in items), default=0)
    return tuple(f"[b]{label + ':':<{width + 1}}[/] {escape(value)}" for label, value in items)


def sections_markup(sections: Iterable[InfoSection]) -> str:
    """Render labelled prose, bullets, commands, and warnings consistently."""

    rendered: list[str] = []
    for section in sections:
        if not section.lines:
            continue
        heading = "[b red]Warning[/]" if section.variant == "warning" else f"[b]{section.title}[/]"
        lines = list(section.lines)
        if section.variant == "commands":
            lines = [f"[reverse] {line} [/]" if line.lstrip().startswith(("rm ", "agent-toolkit-cli")) else line for line in lines]
        rendered.append("\n".join([heading, *lines]))
    return "\n\n".join(rendered)


def compact_detail(value: str, *, limit: int = 58) -> tuple[str, str | None]:
    """Keep a long identifier scannable while retaining it in a later section."""

    if len(value) <= limit:
        return value, None
    head = (limit - 1) // 2
    tail = limit - head - 1
    return f"{value[:head]}…{value[-tail:]}", value


def detail_sections(lines: Iterable[str | InfoFact], *, source: str | None = None) -> tuple[InfoSection, ...]:
    """Classify existing lifecycle guidance without changing its wording.

    ``InfoFact`` keeps raw dynamic values intact through classification,
    compaction, and the single Rich-escaping boundary. Plain strings retain
    their trusted static Rich markup and are split only as legacy prose.
    """

    groups: dict[str, list[str]] = {
        "Source & location": [],
        "Availability": [],
        "Update status": [],
        "Available actions": [],
        "Warning": [],
        "Technical details": [],
    }
    fact_labels = (
        "source path", "symlink target", "catalog", "upstream", "directory",
        "canonical", "location", "pi path", "skill path",
    )

    def add_fact(label: str, value: str) -> None:
        if label.lower() == "source path" and source and value == source:
            return
        summary, full = compact_detail(value)
        groups["Source & location"].append(f"{label}: {escape(summary)}")
        if full:
            groups["Technical details"].append(f"{label}: {escape(full)}")

    for item in lines:
        if isinstance(item, InfoFact):
            if item.label.lower() in fact_labels:
                add_fact(item.label, item.value)
            else:
                groups["Availability"].append(f"{item.label}: {escape(item.value)}")
            continue
        for line in item.splitlines() or [item]:
            if not line:
                continue
            lowered = line.lower().lstrip()
            if lowered.startswith("origin:"):
                continue
            value = line.partition(":")[2].lstrip()
            if lowered.startswith("source path:") and source and value == source:
                continue
            if lowered.startswith("warning:") or "permanently deletes" in lowered:
                groups["Warning"].append(line)
            elif (line.startswith("  rm ") or lowered.startswith(("rm ", "check:", "update:", "space", "ctrl+s", "r →", "remove installation", "manual removal"))):
                groups["Available actions"].append(line)
            elif lowered.startswith(tuple(f"{label}:" for label in fact_labels)) or lowered.startswith("location"):
                label, _, _ = line.partition(":")
                add_fact(label, value)
            elif lowered.startswith(("installed revision", "upstream status", "last checked", "pinned commit")) or "update" in lowered:
                groups["Update status"].append(line)
            else:
                groups["Availability"].append(line)
    variants = {"Available actions": "commands", "Warning": "warning"}
    return tuple(
        InfoSection(title, tuple(group), variants.get(title, "text"))
        for title, group in groups.items() if group
    )


def column_sections(title: str, lines: Iterable[str]) -> tuple[InfoSection, ...]:
    """Give legacy column copy the same labelled hierarchy as asset panes."""

    values = tuple(line for line in lines if line)
    if not values:
        return (InfoSection("At a glance", facts(("Column", title))),)
    bullets = tuple(line for line in values if line.lstrip().startswith("•"))
    prose = tuple(line for line in values if line not in bullets)
    result = [InfoSection("At a glance", facts(("Column", title)))]
    if prose:
        result.append(InfoSection("How it works", prose))
    if bullets:
        result.append(InfoSection("Availability", bullets))
    return tuple(result)
