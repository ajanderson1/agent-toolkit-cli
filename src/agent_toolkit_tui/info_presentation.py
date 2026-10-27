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


def detail_sections(lines: Iterable[str], *, source: str | None = None) -> tuple[InfoSection, ...]:
    """Classify existing lifecycle guidance without changing its wording."""

    groups: dict[str, list[str]] = {
        "Source & location": [],
        "Availability": [],
        "Update status": [],
        "Available actions": [],
        "Warning": [],
        "Technical details": [],
    }
    for item in lines:
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
            elif lowered.startswith(("source path:", "symlink target:", "catalog:", "upstream:", "directory:", "canonical:", "location", "pi path:")):
                label, separator, _ = line.partition(":")
                summary, full = compact_detail(value) if separator else (line, None)
                groups["Source & location"].append(f"{label}:{' ' if separator else ''}{escape(summary)}")
                if full:
                    groups["Technical details"].append(f"{label}: {escape(full)}")
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
