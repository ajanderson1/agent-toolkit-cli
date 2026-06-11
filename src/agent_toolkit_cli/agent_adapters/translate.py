"""Translate mechanism: reshape frontmatter or emit non-md formats to 10 cells.

Per-cell quirks (path-template, required frontmatter, format) live in CELL_PATHS
and the per-emitter functions below.

Sources:
  docs/superpowers/specs/2026-05-28-v3-pr2-agent-facade-and-adapters-design.md
  (Risk Resolution Addendum, translate table, verified 2026-05-28).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.agent_adapters import _guard_foreign, _sentinel_path
from agent_toolkit_cli.skill_agents import UnknownAgentError


# ---------------------------------------------------------------------------
# Path templates
# ---------------------------------------------------------------------------

# {HOME}, {PROJECT}, {SLUG}, {XDG_CONFIG} are placeholders expanded at runtime.
# kilo: global singular "agent/", project plural "agents/" — asymmetric by spec.
# devin: fixed filename AGENT.md; uses "default" profile; XDG_CONFIG global path.
# github-copilot: global ~/.copilot/, project .github/ — different parents.
CELL_PATHS: dict[str, dict[str, str]] = {
    "codex":          {"global": "{HOME}/.codex/agents/{SLUG}.toml",
                       "project": "{PROJECT}/.codex/agents/{SLUG}.toml"},
    "devin":          {"global": "{XDG_CONFIG}/devin/agents/default/AGENT.md",
                       "project": "{PROJECT}/.devin/agents/default/AGENT.md"},
    "gemini-cli":     {"global": "{HOME}/.gemini/agents/{SLUG}.md",
                       "project": "{PROJECT}/.gemini/agents/{SLUG}.md"},
    "github-copilot": {"global": "{HOME}/.copilot/agents/{SLUG}.agent.md",
                       "project": "{PROJECT}/.github/agents/{SLUG}.agent.md"},
    "kilo":           {"global": "{XDG_CONFIG}/kilo/agent/{SLUG}.md",
                       "project": "{PROJECT}/.kilo/agents/{SLUG}.md"},
    "kiro-cli":       {"global": "{HOME}/.kiro/agents/{SLUG}.json",
                       "project": "{PROJECT}/.kiro/agents/{SLUG}.json"},
    "mistral-vibe":   {"global": "{HOME}/.vibe/agents/{SLUG}.toml",
                       "project": "{PROJECT}/.vibe/agents/{SLUG}.toml"},
    "mux":            {"global": "{HOME}/.mux/agents/{SLUG}.md",
                       "project": "{PROJECT}/.mux/agents/{SLUG}.md"},
    "opencode":       {"global": "{XDG_CONFIG}/opencode/agents/{SLUG}.md",
                       "project": "{PROJECT}/.opencode/agents/{SLUG}.md"},
    "qwen-code":      {"global": "{HOME}/.qwen/agents/{SLUG}.md",
                       "project": "{PROJECT}/.qwen/agents/{SLUG}.md"},
}

_VALID_SCOPES = frozenset({"global", "project"})


# ---------------------------------------------------------------------------
# Path expansion — fail-loud on missing args
# ---------------------------------------------------------------------------

def _expand(
    template: str,
    *,
    home: Path | None,
    project: Path | None,
    slug: str,
) -> Path:
    """Expand {HOME}/{PROJECT}/{SLUG}/{XDG_CONFIG} placeholders.

    Fail-loud: if the template needs {HOME} or {PROJECT} but the corresponding
    arg is None, raise ValueError rather than leaving a literal placeholder in
    the path (which would silently write to `./{HOME}/...` under cwd).

    {XDG_CONFIG}: reads XDG_CONFIG_HOME env first; falls back to home/.config;
    raises ValueError if both env is unset AND home is None.
    """
    out = template.replace("{SLUG}", slug)

    if "{HOME}" in out:
        if home is None:
            raise ValueError(
                f"translate._expand: template {template!r} requires home= but None was passed"
            )
        out = out.replace("{HOME}", str(home))

    if "{PROJECT}" in out:
        if project is None:
            raise ValueError(
                f"translate._expand: template {template!r} requires project= but None was passed"
            )
        out = out.replace("{PROJECT}", str(project))

    if "{XDG_CONFIG}" in out:
        xdg_env = os.environ.get("XDG_CONFIG_HOME")
        if xdg_env:
            out = out.replace("{XDG_CONFIG}", xdg_env)
        elif home is not None:
            out = out.replace("{XDG_CONFIG}", str(home / ".config"))
        else:
            raise ValueError(
                f"translate._expand: template {template!r} requires home= to resolve "
                "{XDG_CONFIG} (XDG_CONFIG_HOME env is unset and home= is None)"
            )

    return Path(out)


# ---------------------------------------------------------------------------
# Minimal frontmatter parser
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^\s+-\s+(.+)$")


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and body from a markdown document.

    Handles:
    - Scalar values:  ``key: value``
    - List values:    ``key:\\n  - item1\\n  - item2``

    Returns (fm_dict, body). If no frontmatter block is found, returns
    ({}, text).
    """
    m = _FM_RE.match(text)
    if not m:
        return {}, text

    fm_raw = m.group(1)
    body = text[m.end():]

    fm: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in fm_raw.splitlines():
        # List item continuation
        if current_list is not None:
            li = _LIST_ITEM_RE.match(line)
            if li:
                current_list.append(li.group(1))
                continue
            else:
                # End of list — flush
                fm[current_key] = current_list  # type: ignore[index]
                current_key = None
                current_list = None

        # Key: value or key: (start of list)
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                # Next lines may be list items
                current_key = key
                current_list = []
            else:
                fm[key] = val
        # else: unrecognised continuation — skip

    # Flush any trailing list
    if current_key is not None and current_list is not None:
        fm[current_key] = current_list

    return fm, body


def _emit_yaml_frontmatter(fm: dict[str, Any], body: str) -> str:
    """Serialise fm as YAML frontmatter block + body."""
    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


# ---------------------------------------------------------------------------
# Per-emitter functions
# ---------------------------------------------------------------------------

# gemini-cli: yaml-strict — only documented fields pass through.
_GEMINI_ALLOWED = frozenset({
    "name", "description", "display_name", "tools", "mcp_servers",
    "model", "temperature", "max_turns", "timeout_mins", "kind",
})


def _emit_gemini_strict(fm: dict[str, Any], body: str, slug: str) -> str:
    filtered = {k: v for k, v in fm.items() if k in _GEMINI_ALLOWED}
    return _emit_yaml_frontmatter(filtered, body)


# yaml-passthrough emitters — devin
def _emit_devin(fm: dict[str, Any], body: str, slug: str) -> str:
    return _emit_yaml_frontmatter(fm, body)


# github-copilot: description required; optional pass-through fields only.
_COPILOT_ALLOWED = frozenset({
    "name", "description", "target", "tools", "model",
    "disable-model-invocation", "user-invocable", "infer",
    "mcp-servers", "metadata",
})


def _emit_github_copilot(fm: dict[str, Any], body: str, slug: str) -> str:
    if "description" not in fm:
        raise ValueError(
            "github-copilot: 'description' is required in frontmatter but was not found"
        )
    filtered = {k: v for k, v in fm.items() if k in _COPILOT_ALLOWED}
    return _emit_yaml_frontmatter(filtered, body)


# opencode + kilo: inject mode: subagent
def _emit_opencode_or_kilo(fm: dict[str, Any], body: str, slug: str) -> str:
    merged = dict(fm)
    merged["mode"] = "subagent"
    return _emit_yaml_frontmatter(merged, body)


# qwen-code: strip systemPrompt key; body IS the system prompt (not a key).
def _emit_qwen_code(fm: dict[str, Any], body: str, slug: str) -> str:
    filtered = {k: v for k, v in fm.items() if k != "systemPrompt"}
    return _emit_yaml_frontmatter(filtered, body)


# mux: strip flat runnable; emit subagent:\n  runnable: true block.
def _emit_mux(fm: dict[str, Any], body: str, slug: str) -> str:
    filtered = {k: v for k, v in fm.items() if k != "runnable"}
    text = _emit_yaml_frontmatter(filtered, body)
    # Re-open frontmatter to inject the nested block.
    # The subagent block must be inside the --- delimiters.
    if text.startswith("---\n"):
        rest = text[4:]  # strip leading ---\n
        # Find the closing ---
        close_idx = rest.find("\n---\n")
        if close_idx != -1:
            fm_section = rest[:close_idx]
            after = rest[close_idx + 1:]  # keeps ---\n and body
            nested = "subagent:\n  runnable: true"
            text = "---\n" + fm_section + "\n" + nested + "\n" + after
    return text


# codex: toml with developer_instructions from body.
def _emit_codex_toml(fm: dict[str, Any], body: str, slug: str) -> str:
    lines = []
    lines.append(f'name = {_toml_str(fm.get("name", slug))}')
    lines.append(f'description = {_toml_str(fm.get("description", ""))}')
    if "model" in fm:
        lines.append(f'model = {_toml_str(fm["model"])}')
    lines.append(f'developer_instructions = {_toml_multiline(body)}')
    return "\n".join(lines) + "\n"


# mistral-vibe: toml with required agent_type, display_name, description, safety, enabled_tools.
_VALID_SAFETY = frozenset({"safe", "neutral", "destructive", "yolo"})


def _emit_mistral_vibe_toml(fm: dict[str, Any], body: str, slug: str) -> str:
    safety = fm.get("safety", "neutral")
    if safety not in _VALID_SAFETY:
        raise ValueError(
            f"mistral-vibe: safety must be one of {sorted(_VALID_SAFETY)}, got {safety!r}"
        )
    tools = fm.get("tools", [])
    if isinstance(tools, str):
        tools = [tools]
    lines = [
        'agent_type = "subagent"',
        f'display_name = {_toml_str(fm.get("display_name", fm.get("name", slug)))}',
        f'description = {_toml_str(fm.get("description", ""))}',
        f'safety = {_toml_str(safety)}',
        f'enabled_tools = {_toml_array(tools)}',
    ]
    return "\n".join(lines) + "\n"


# kiro-cli: json with name, description, prompt (body), optional model + tools.
def _emit_kiro_json(fm: dict[str, Any], body: str, slug: str) -> str:
    data: dict[str, Any] = {
        "name": fm.get("name", slug),
        "description": fm.get("description", ""),
        "prompt": body,
    }
    if "model" in fm:
        data["model"] = fm["model"]
    if "tools" in fm:
        tools = fm["tools"]
        data["tools"] = tools if isinstance(tools, list) else [tools]
    return json.dumps(data, indent=2) + "\n"


# ---------------------------------------------------------------------------
# TOML helpers (write-side; tomllib is read-only stdlib)
# ---------------------------------------------------------------------------

def _toml_str(value: Any) -> str:
    """Encode a scalar as a TOML basic string."""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_multiline(value: str) -> str:
    """Encode a multiline string as a TOML multi-line basic string."""
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'"""{escaped}"""'


def _toml_array(items: list[str]) -> str:
    """Encode a list of strings as a TOML inline array."""
    encoded = ", ".join(_toml_str(i) for i in items)
    return f"[{encoded}]"


# ---------------------------------------------------------------------------
# Emitter dispatch table
# ---------------------------------------------------------------------------

_EMITTERS: dict[str, Callable[[dict[str, Any], str, str], str]] = {
    "codex":          _emit_codex_toml,
    "devin":          _emit_devin,
    "gemini-cli":     _emit_gemini_strict,
    "github-copilot": _emit_github_copilot,
    "kilo":           _emit_opencode_or_kilo,
    "kiro-cli":       _emit_kiro_json,
    "mistral-vibe":   _emit_mistral_vibe_toml,
    "mux":            _emit_mux,
    "opencode":       _emit_opencode_or_kilo,
    "qwen-code":      _emit_qwen_code,
}


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------

class _TranslateAdapter:
    """Per-harness adapter: reads canonical .md, emits reshaped content."""

    def __init__(self, harness: str):
        if harness not in CELL_PATHS:
            raise UnknownAgentError(harness)
        self.harness = harness
        self._cell = CELL_PATHS[harness]
        self._emitter = _EMITTERS[harness]

    def _resolve_dest(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None,
        project: Path | None,
    ) -> Path:
        """Validate scope + expand the cell's template, fail-loud on bad input."""
        if scope not in _VALID_SCOPES:
            raise ValueError(
                f"{self.harness}: scope must be 'global' or 'project', got {scope!r}"
            )
        return _expand(self._cell[scope], home=home, project=project, slug=slug)

    def destination(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
    ) -> Path:
        """Return the on-disk path this adapter installs to. Read-only.

        Used by the facade's agent-aware 'currently linked' scan to test
        whether this harness already holds a projection (dest.exists()).
        """
        return self._resolve_dest(slug, scope=scope, home=home, project=project)

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        # Fail loud on a missing canonical content file (standard-adapter F8
        # parity) BEFORE read_text raises a raw OSError mid-fan-out.
        if not content_path.exists():
            raise InstallError(
                f"{self.harness}: {slug}: canonical content file missing: "
                f"{content_path} — re-run `agent add {slug}` to restore it"
            )
        raw = content_path.read_text()
        try:
            fm, body = _parse_frontmatter(raw)
            output = self._emitter(fm, body, slug)
        except ValueError as exc:
            # Data-dependent translation failure (missing/invalid frontmatter).
            # Emitter messages already name the harness and key; InstallError
            # is what the CLI layer converts to a clean ClickException.
            raise InstallError(str(exc)) from exc
        # Adopt-if-identical (#368): "identical" for translate means the file
        # matches what the emitter would write NOW (emission-identical) — the
        # destination never holds the canonical bytes. Compare BYTES, not
        # decoded text: a foreign non-UTF8 file at the destination must route
        # to the conflict branch below, not raise UnicodeDecodeError.
        if dest.exists() and not dest.is_symlink() and dest.read_bytes() == output.encode():
            _sentinel_path(dest).write_text("")
            return dest
        # Ownership = SENTINEL, not lock (#368, standard-adapter parity; G5).
        _guard_foreign(dest, harness=self.harness, overwrite=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Replace, never write through, a symlink at the slot (F6 parity).
        if dest.is_symlink():
            dest.unlink()
        dest.write_text(output)
        _sentinel_path(dest).write_text("")
        return dest

    def _emitted_or_none(
        self, canonical_content: Path | None, slug: str,
    ) -> str | None:
        """Re-run the emitter over the canonical for content-match detach.
        Any failure (absent file, unreadable, emitter ValueError) returns
        None — uninstall must never crash computing ownership; the sidecar
        alone then decides."""
        if canonical_content is None or not canonical_content.exists():
            return None
        try:
            fm, body = _parse_frontmatter(canonical_content.read_text())
            return self._emitter(fm, body, slug)
        except (ValueError, OSError):
            return None

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        """Ownership-guarded detach (#368): unlink when the sentinel exists
        OR the file matches what the emitter would write now (covers
        pre-sentinel installs). Foreign files are left in place and returned
        as a structured refusal. The sidecar is removed whenever the file is
        gone (orphan hygiene — translate previously cleaned nothing)."""
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        sentinel = _sentinel_path(dest)
        refused: Path | None = None
        if dest.exists() or dest.is_symlink():
            owned = sentinel.exists()
            if not owned and not dest.is_symlink():
                expected = self._emitted_or_none(canonical_content, slug)
                # Bytes compare + OSError guard: a foreign non-UTF8 or
                # unreadable file must refuse, never crash the detach.
                try:
                    owned = (expected is not None
                             and dest.read_bytes() == expected.encode())
                except OSError:
                    owned = False
            if owned:
                dest.unlink()
            else:
                refused = dest
                print(
                    f"{self.harness}: {dest} not managed by this tool "
                    f"(no sentinel, content differs) — left in place",
                    file=sys.stderr,
                )
        if sentinel.exists() and not dest.exists():
            sentinel.unlink()
        return refused


def adapter_for(harness: str) -> _TranslateAdapter:
    """Return the translate-mechanism adapter for `harness`."""
    return _TranslateAdapter(harness)
