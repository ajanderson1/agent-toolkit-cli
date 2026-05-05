"""Cross-asset dependency enforcement for `spec.requires`.

The schema allows an asset to declare peer dependencies per harness:

    spec:
      requires:
        pi: ["pi-extension:pi-subagents", "skill:foo"]

The canonical form for `<kind>:<slug>` strings is defined by the schema
pattern `^(skill|agent|command|hook|plugin|mcp|pi-extension):[a-z0-9][a-z0-9-]*$`.
The kind token MUST be the full schema kind name — `pi-extension`, not the
shorthand `extension`.  The SSOT matrix doc example uses `extension:pi-subagents`
which is a doc inconsistency; the schema is authoritative.

`validate_requires` is called from the projection path (project_from_file) and
exits 2 if any declared peer for the requested harness is absent from the
allowlist.
"""
from __future__ import annotations

import click

from agent_toolkit._allowlist import kind_to_section


class RequiresUnsatisfied(Exception):
    """Raised when an asset's spec.requires peers are absent from the allowlist.

    Carry the structured fields so callers can format messages or surface them
    in structured CLI errors — mirrors UnsupportedPair in _support.py.
    """

    def __init__(
        self,
        asset_slug: str,
        asset_kind: str,
        harness: str,
        missing: list[tuple[str, str]],
    ) -> None:
        self.asset_slug = asset_slug
        self.asset_kind = asset_kind
        self.harness = harness
        self.missing = missing  # list of (kind, slug) tuples
        missing_str = ", ".join(f"{k}:{s}" for k, s in missing)
        super().__init__(
            f"asset {asset_kind}:{asset_slug} requires {missing_str} on harness"
            f" {harness} but they are not in the allowlist"
        )


def parse_requires_entries(raw: list[str]) -> list[tuple[str, str]]:
    """Parse ['pi-extension:pi-subagents', 'skill:foo'] into (kind, slug) tuples.

    The canonical kind token is the full schema kind name: 'pi-extension', not
    the shorthand 'extension'.  Entries that do not match the expected
    'kind:slug' shape are returned with an empty string as the kind so callers
    can treat them as validation errors.
    """
    result: list[tuple[str, str]] = []
    for entry in raw:
        if ":" not in entry:
            result.append(("", entry))
            continue
        kind, _, slug = entry.partition(":")
        result.append((kind.strip(), slug.strip()))
    return result


def validate_requires(
    ctx: click.Context,
    asset_slug: str,
    asset_kind: str,
    harness: str,
    scope: str,
    requires: dict[str, list[str]],
    allowed: dict[str, list[str]],
) -> None:
    """Exit 2 with a structured stderr message if any spec.requires peer for
    `harness` is absent from `allowed`.

    `requires` is the asset's `spec.requires` dict (harness -> list of
    'kind:slug' strings).  `allowed` is the parsed allowlist dict (section ->
    list of slugs) as returned by `read_allowlist`.  `scope` is 'user' or
    'project', used in the fix hint.

    When all peers are satisfied (or there are no peers for this harness) this
    function is a no-op.
    """
    peers_raw = requires.get(harness) or []
    if not peers_raw:
        return

    missing: list[tuple[str, str]] = []
    for peer_kind, peer_slug in parse_requires_entries(peers_raw):
        if not peer_kind:
            # Malformed entry — treat as missing so the user sees it.
            missing.append(("", peer_slug))
            continue
        try:
            section = kind_to_section(peer_kind)
        except ValueError:
            # Unknown kind — treat as missing.
            missing.append((peer_kind, peer_slug))
            continue
        allowed_slugs = set(allowed.get(section) or [])
        if peer_slug not in allowed_slugs:
            missing.append((peer_kind, peer_slug))

    if not missing:
        return

    missing_str = ", ".join(
        f"{k}:{s}" if k else s for k, s in missing
    )
    first_kind, first_slug = missing[0]

    if first_kind:
        try:
            first_section = kind_to_section(first_kind)
        except ValueError:
            first_section = None
    else:
        first_section = None

    section_hint = f"under [{first_section}]" if first_section else "in the appropriate section"
    fix_hint = (
        f"run `agent-toolkit link {scope} {harness} {first_kind}:{first_slug}` first"
        if first_kind
        else "add the missing asset to the allowlist"
    )

    click.echo(
        f"{asset_kind}:{asset_slug} requires {missing_str} on {harness} — "
        f"add it to the allowlist {section_hint} or {fix_hint}.",
        err=True,
    )
    ctx.exit(2)
