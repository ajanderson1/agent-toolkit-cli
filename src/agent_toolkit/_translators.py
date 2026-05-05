"""Per-(harness, kind) translators producing harness-flavored markdown bytes.

A translator is a pure function `(record, body) -> bytes` consulted by
`commands/_link_lib.maybe_link` when projecting an asset into a harness
whose runtime frontmatter shape differs from the toolkit's wrapper.

The output is written to a per-scope cache directory; the harness slot
symlink targets the cache file. See
`docs/superpowers/specs/2026-05-05-phase3-translate-design.md`.
"""
from __future__ import annotations

from typing import Callable

import yaml

from agent_toolkit.walker import AssetRecord


def _render(frontmatter: dict, body: str) -> bytes:
    """Compose `---\\n<yaml>---\\n<body>` and return UTF-8 bytes.

    `yaml.safe_dump(..., sort_keys=False)` is required so the key order in
    the output is stable across Python versions and matches the order we
    constructed the dict in.
    """
    fm_text = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    return f"---\n{fm_text}---\n{body}".encode("utf-8")


def _wrapper_block(record: AssetRecord) -> dict:
    """Verbatim subset of the source frontmatter, preserved under `agent_toolkit:`."""
    md = record.metadata
    block: dict = {"apiVersion": md.get("apiVersion")}
    if "metadata" in md:
        block["metadata"] = md["metadata"]
    if "spec" in md:
        block["spec"] = md["spec"]
    return block


def _description(record: AssetRecord) -> str:
    return (record.metadata.get("metadata") or {}).get("description") or ""


def _translate_opencode_agent(record: AssetRecord, body: str) -> bytes:
    fm = {
        "description": _description(record),
        "mode": "subagent",
        "agent_toolkit": _wrapper_block(record),
    }
    return _render(fm, body)


def _translate_opencode_command(record: AssetRecord, body: str) -> bytes:
    fm = {
        "description": _description(record),
        "agent_toolkit": _wrapper_block(record),
    }
    return _render(fm, body)


TRANSLATORS: dict[tuple[str, str], Callable[[AssetRecord, str], bytes]] = {
    ("opencode", "agent"): _translate_opencode_agent,
    ("opencode", "command"): _translate_opencode_command,
}
