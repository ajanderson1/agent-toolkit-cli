"""Per-(harness, kind) translators producing harness-flavored markdown bytes.

A translator is a pure function `(record, body) -> bytes` consulted by
`commands/_link_lib.maybe_link` when projecting an asset into a harness
whose runtime frontmatter shape differs from the toolkit's wrapper.

The output is written to a per-scope cache directory; the harness slot
symlink targets the cache file. See
`docs/superpowers/specs/2026-05-05-phase3-translate-design.md`.
"""
from __future__ import annotations

import json
from typing import Callable

import yaml

from agent_toolkit_cli.walker import AssetRecord


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
    """Verbatim subset of the source frontmatter, preserved under `agent_toolkit_cli:`."""
    md = record.metadata
    block: dict = {"apiVersion": md.get("apiVersion")}
    if "metadata" in md:
        block["metadata"] = md["metadata"]
    if "spec" in md:
        block["spec"] = md["spec"]
    return block


def _description(record: AssetRecord) -> str:
    return (record.metadata.get("metadata") or {}).get("description") or ""


def _name(record: AssetRecord) -> str:
    return (record.metadata.get("metadata") or {}).get("name") or ""


def _translate_opencode_agent(record: AssetRecord, body: str) -> bytes:
    fm = {
        "description": _description(record),
        "mode": "subagent",
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)


def _translate_opencode_command(record: AssetRecord, body: str) -> bytes:
    fm = {
        "description": _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)


def _translate_codex_skill(record: AssetRecord, body: str) -> bytes:
    """Codex skills require `description:` at the YAML top level. The toolkit's
    v1alpha2 wrapper nests it under `metadata.description`, so the loader rejects
    every skill with `failed to load skill ... missing field 'description'` (#40).

    Output mirrors `_translate_opencode_command` exactly — top-level `description`
    plus `agent_toolkit_cli` wrapper for round-trip traceability. Empirically verified
    against codex 0.128.0: extra top-level keys are tolerated.
    """
    fm = {
        "description": record.harness_description or _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)


def _translate_opencode_skill(record: AssetRecord, body: str) -> bytes:
    """OpenCode skills require BOTH `name:` AND `description:` at the YAML top
    level — `add()` does `z.object({ name, description }).safeParse(md.data)`
    and silently skips skills that fail validation (#41).

    Output mirrors `_translate_codex_skill` plus a top-level `name` field.
    Empirically verified against opencode 1.14.30: skills with this shape
    are loaded by `opencode debug skill`; skills with the raw v1alpha2
    wrapper (no top-level name/description) are silently dropped.
    """
    fm = {
        "name": record.asset.slug,
        "description": record.harness_description or _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)


def _translate_pi_skill(record: AssetRecord, body: str) -> bytes:
    """Pi skills require `description:` at the YAML top level (per the
    `pi demands` error `description is required`). Optionally accepts
    `argument-hint:` for arg-aware skills; that field is sourced from
    `spec.per_harness.pi.argument_hint` if present on the sidecar.

    Output mirrors `_translate_opencode_skill`: top-level `name`,
    `description`, optional `argument-hint`, plus the `agent_toolkit_cli`
    wrapper for round-trip traceability.
    """
    description = record.harness_description or _description(record)
    pi_extras = ((record.metadata.get("spec") or {}).get("per_harness") or {}).get("pi") or {}
    fm: dict = {
        "name": record.asset.slug,
        "description": description,
    }
    if "argument_hint" in pi_extras:
        fm["argument-hint"] = pi_extras["argument_hint"]
    fm["agent_toolkit_cli"] = _wrapper_block(record)
    return _render(fm, body)


def _translate_gemini_agent(record: AssetRecord, body: str) -> bytes:
    """Gemini's loader (packages/core/src/agents/agentLoader.ts) validates
    frontmatter with zod `.strict()` — extra top-level keys cause silent
    rejection. The toolkit's v1alpha2 wrapper, when emitted as a frontmatter
    key, makes every linked agent invisible to Gemini's `/agents` registry.

    Output is therefore minimal: top-level `name` and `description` only —
    no `agent_toolkit_cli` wrapper. The wrapper's metadata still lives in
    the source asset and is recoverable via the toolkit's walker; the cache
    file is a one-way render for Gemini's runtime, not a round-trip carrier.

    This is a deliberate departure from `_translate_opencode_agent` /
    `_translate_opencode_skill`, which both keep the wrapper because OpenCode
    uses non-strict zod validation. Empirically verified against gemini
    0.40.1: wrapper-bearing frontmatter is dropped from `/agents list`;
    minimal frontmatter loads cleanly (#97).
    """
    fm = {
        "name": _name(record),
        "description": _description(record),
    }
    return _render(fm, body)


def _translate_codex_agent(record: AssetRecord, body: str) -> bytes:
    """Emit a Codex subagents TOML agent file.

    Codex subagents live at `~/.codex/agents/<name>.toml` (and
    `<project>/.codex/agents/<name>.toml`). The required TOML fields are
    `name`, `description`, and `developer_instructions`.

    The `name` field uses the asset slug (= slot filename stem) — not
    `metadata.name` — so the slot filename and the TOML name field stay in
    sync. Codex's loader derives the agent name from the filename by
    convention; mismatches would cause silent-skip or name collisions.

    We additionally emit an `[agent_toolkit_cli]` table for round-trip
    traceability, mirroring `_translate_gemini_command`'s pattern exactly.
    """
    md = record.metadata
    # Use the asset slug as the TOML name so filename ↔ name stay in sync.
    slug = record.asset.slug
    description = (md.get("metadata") or {}).get("description") or ""
    api_version = md.get("apiVersion") or ""
    metadata_block = md.get("metadata") or {}
    spec_block = md.get("spec")

    parts: list[str] = []
    parts.append(f"name = {_toml_basic_string(slug)}\n")
    parts.append(f"description = {_toml_basic_string(description)}\n")
    parts.append(f"developer_instructions = {_toml_multiline_string(body)}\n")
    parts.append("\n[agent_toolkit_cli]\n")
    parts.append(f"apiVersion = {_toml_basic_string(api_version)}\n")
    parts.append(
        f"metadata = {_toml_basic_string(json.dumps(metadata_block, sort_keys=True))}\n"
    )
    if spec_block is not None:
        parts.append(
            f"spec = {_toml_basic_string(json.dumps(spec_block, sort_keys=True))}\n"
        )
    return "".join(parts).encode("utf-8")


def _translate_gemini_command(record: AssetRecord, body: str) -> bytes:
    """Emit a Gemini-flavored TOML command file.

    Gemini's custom commands live at `~/.gemini/commands/<name>.toml` (and
    `<project>/.gemini/commands/<name>.toml`). The v1 TOML schema requires
    `prompt` and accepts an optional `description`.

    We additionally emit an `[agent_toolkit_cli]` table so the rendered file
    can be traced back to its toolkit source. The wrapper's `metadata` and
    `spec` blocks (free-form dicts) are JSON-encoded as TOML strings —
    lossless round-trip via `tomllib.loads(...)` + `json.loads(...)`. This is
    deliberately ugly: TOML cannot natively represent the wrapper's nested
    free-form shape, and we'd rather have a stable text-string than risk a
    schema-versioning footgun by inventing a half-flattened TOML structure.
    """
    md = record.metadata
    description = (md.get("metadata") or {}).get("description") or ""
    api_version = md.get("apiVersion") or ""
    metadata_block = md.get("metadata") or {}
    spec_block = md.get("spec")

    parts: list[str] = []
    parts.append(f"description = {_toml_basic_string(description)}\n")
    parts.append(f"prompt = {_toml_multiline_string(body)}\n")
    parts.append("\n[agent_toolkit_cli]\n")
    parts.append(f"apiVersion = {_toml_basic_string(api_version)}\n")
    # metadata/spec are always JSON-serializable: the walker parses YAML
    # frontmatter (scalars, lists, dicts) — no datetime/Path/custom types.
    parts.append(
        f"metadata = {_toml_basic_string(json.dumps(metadata_block, sort_keys=True))}\n"
    )
    if spec_block is not None:
        parts.append(
            f"spec = {_toml_basic_string(json.dumps(spec_block, sort_keys=True))}\n"
        )
    return "".join(parts).encode("utf-8")


def _toml_basic_string(s: str) -> str:
    """Render a TOML basic string with `"` and `\\` escaped.

    Spec: https://toml.io/en/v1.0.0#string . Basic strings use `"..."`;
    inside them, `\\` and `"` must be escaped, as must control characters.
    Newlines force the multiline form — callers that may include newlines
    must use `_toml_multiline_string` instead.
    """
    if "\n" in s or "\r" in s:
        # Defensive: callers should pick the multiline variant for these.
        # Fall through to the multiline emitter rather than risk an
        # invalid one-liner.
        return _toml_multiline_string(s)
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_multiline_string(s: str) -> str:
    r"""Render a TOML multi-line basic string (`\"\"\"...\"\"\"`).

    The only character that breaks this form is a `\"\"\"` substring inside the
    payload — escape the third `"` so the lexer stops at two `"`s.
    Backslashes must also be escaped. A leading newline is omitted by the
    spec when it's the first character after the opening `\"\"\"`, but we
    explicitly insert one so the rendered file is human-friendly.
    """
    # Escape backslashes first to avoid double-escaping our own escape.
    escaped = s.replace("\\", "\\\\")
    # Then break any internal `"""` by escaping the third quote.
    escaped = escaped.replace('"""', '""\\"')
    return f'"""\n{escaped}"""'


TRANSLATORS: dict[tuple[str, str], Callable[[AssetRecord, str], bytes]] = {
    ("opencode", "agent"): _translate_opencode_agent,
    ("opencode", "command"): _translate_opencode_command,
    ("codex", "agent"): _translate_codex_agent,
    ("codex", "skill"): _translate_codex_skill,
    ("opencode", "skill"): _translate_opencode_skill,
    ("pi", "skill"): _translate_pi_skill,
    ("gemini", "command"): _translate_gemini_command,
    ("gemini", "agent"): _translate_gemini_agent,
}
