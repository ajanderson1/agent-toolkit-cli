"""Pure helpers for link/unlink/diff subcommands.

No Click, no I/O orchestration — just projection algorithm, action counting,
output-string formatters, and the plan-mode line iterator. Each function is
unit-tested in tests/test_link_lib.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass
class LinkCounters:
    created: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    would_link: int = 0
    would_unlink: int = 0


def format_summary(c: LinkCounters, dry_run: bool) -> str:
    if dry_run:
        total = c.would_link + c.would_unlink
        if total == 0:
            return "Nothing to change."
        return (
            f"{total} changes pending ({c.would_link} to link, "
            f"{c.would_unlink} to remove). Re-run without --dry-run to apply."
        )
    changed = c.created + c.updated + c.removed
    if changed == 0:
        return f"Already in sync — {c.unchanged} assets linked, nothing to change."
    return (
        f"Linked {c.created} new, updated {c.updated}, removed "
        f"{c.removed} stale ({c.unchanged} already in sync)."
    )


MALFORMED = "__malformed__"


def iter_plan_lines(text: str) -> Iterator[tuple[str, str]]:
    """Yield (kind, slug) pairs from --plan stdin text.

    - Strips `#`-comments (anything from `#` to end-of-line).
    - Skips blank-after-strip lines.
    - For lines without a colon, yields (MALFORMED, raw_line) — the original
      pre-strip line, so callers can render the user's input verbatim in
      diagnostics. Caller should not re-parse it.
    """
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            yield (MALFORMED, raw)
            continue
        kind, _, slug = line.partition(":")
        yield (kind.strip(), slug.strip())
