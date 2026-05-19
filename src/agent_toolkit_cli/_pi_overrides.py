# src/agent_toolkit_cli/_pi_overrides.py
"""Pi extensions[] override evaluator.

Mirrors `isEnabledByOverrides` from `@earendil-works/pi-coding-agent`
`dist/core/package-manager.js:502`. Inputs are a slug (auto-discovery dir
name) and the verbatim `extensions[]` list from settings.json.

Pattern grammar (per `getOverridePatterns`, `:499` and `applyPatterns`, `:527`):
- plain entry → include-filter (only matching slugs enabled when present)
- `!entry`    → exclude
- `+entry`    → force-include (overrides excludes)
- `-entry`    → force-exclude (overrides force-includes)

Matching is exact-name + `*` glob only — narrower than Pi's full glob engine
(which matches paths, not slugs). Anything more elaborate is treated as
non-matching here; the doctor advisory surfaces patterns that don't match any
known slug.
"""
from __future__ import annotations

import fnmatch


def _matches(slug: str, pattern: str) -> bool:
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatchcase(slug, pattern)
    return slug == pattern


def is_enabled(*, slug: str, overrides: list[str]) -> bool:
    plain: list[str] = []
    excludes: list[str] = []
    force_includes: list[str] = []
    force_excludes: list[str] = []
    for entry in overrides:
        if entry.startswith("!"):
            excludes.append(entry[1:])
        elif entry.startswith("+"):
            force_includes.append(entry[1:])
        elif entry.startswith("-"):
            force_excludes.append(entry[1:])
        else:
            plain.append(entry)

    if plain:
        enabled = any(_matches(slug, p) for p in plain)
    else:
        enabled = True

    if excludes and any(_matches(slug, p) for p in excludes):
        enabled = False
    if force_includes and any(_matches(slug, p) for p in force_includes):
        enabled = True
    if force_excludes and any(_matches(slug, p) for p in force_excludes):
        enabled = False
    return enabled
