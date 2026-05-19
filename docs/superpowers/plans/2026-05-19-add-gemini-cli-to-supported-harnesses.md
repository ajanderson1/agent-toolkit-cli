# Add Gemini CLI to supported harnesses — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `gemini` as the fifth supported harness in agent-toolkit-cli at full parity with claude — skill, agent, command, and a real `ConfigFileAdapter` for MCP — including a new TOML translator for Gemini commands.

**Architecture:** Single PR. Mechanical registry additions to `_support.py` and `harness_adapters/__init__.py`; a new `harness_adapters/gemini.py` modelled on `claude.py` (camelCase `mcpServers` key in `~/.gemini/settings.json`); a new `_translate_gemini_command` translator that emits TOML (Gemini's command format) with a JSON-encoded `[agent_toolkit_cli]` wrapper for round-trip traceability; small additions in `commands/_link_lib.py` so the cache/slot machinery handles `.toml` files; doc + matrix + test updates.

**Tech Stack:** Python 3.11+, stdlib `tomllib`/`json`, pytest, click. No new third-party dependencies. Hand-emit the small TOML shape we need (avoids adding `tomli_w`).

**Spec:** `docs/superpowers/specs/2026-05-19-add-gemini-cli-to-supported-harnesses-design.md` (commit `4256c52`).

**Issue:** [#53](https://github.com/ajanderson1/agent-toolkit-cli/issues/53).

**Tuple order chosen:** `("claude", "codex", "opencode", "gemini", "pi")` — gemini sits before `pi` (gemini ships a real adapter; pi remains the placeholder-only entry at the tail).

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `src/agent_toolkit_cli/_support.py` | Modify | `ALL_HARNESSES` tuple gains `gemini`; `_USER_TARGETS` / `_PROJECT_TARGETS` gain 4 rows each |
| `src/agent_toolkit_cli/harness_adapters/__init__.py` | Modify | `_KNOWN_HARNESSES` gains `gemini`; `get_adapter` gains a real-adapter branch |
| `src/agent_toolkit_cli/harness_adapters/gemini.py` | Create | `GeminiAdapter` — `ConfigFileAdapter` against `~/.gemini/settings.json` (user) and `<root>/.gemini/settings.json` (project), top-level key `mcpServers` |
| `src/agent_toolkit_cli/_translators.py` | Modify | New `_translate_gemini_command(record, body) -> bytes` emitting TOML; registered in `TRANSLATORS` |
| `src/agent_toolkit_cli/commands/_link_lib.py` | Modify | `HARNESS_HOMES` gains `gemini`; `_CACHE_LAYOUT` gains `gemini`; `_translated_slot_filename` gains a hard branch for `(gemini, command)` → `f"{slug}.toml"`; `_translate_slot_layout` gains a hard branch for `(gemini, command)` → `"file"` |
| `src/agent_toolkit_cli/doctor/harness_homes.py` | Modify | Summary string derived from `len(ALL_HARNESSES)` |
| `docs/agent-toolkit/harness-matrix.md` | Modify | Gain `Gemini` column with cells for all 7 kinds |
| `README.md` | Modify | List Gemini CLI in the supported set; refresh MCP-status note |
| `tests/test_support.py` | Modify | Canary tuple update; new spot-checks for `(gemini, *)` cells |
| `tests/test_harness_matrix.py` | Modify | `_HARNESS_ORDER` and `_ROW_RE` named-group regex extended; `_TRANSLATE_PATH_RE` extended to allow `commands/<slug>.toml` |
| `tests/test_translators.py` | Modify | New cases for `_translate_gemini_command` (minimum, with wrapper, with triple-quoted body) |
| `tests/test_link_lib.py` | Modify | New assertions for `(gemini, command)` in `_translated_slot_filename` and `_translate_slot_layout` |
| `tests/test_mcp_adapters_gemini.py` | Create | Mirrors `test_mcp_adapters_claude.py` shape — `config_target`, `list_installed`, `entry_drift`, `diff` round-trip |

### Decision: hard-branch vs `endswith` extension

The spec flagged a choice between extending `endswith(".md")` to `endswith((".md", ".toml"))` versus a hard branch on `(harness, kind)`. **This plan picks the hard branch**, in both `_translated_slot_filename` and `_translate_slot_layout`. Rationale: the existing function structure already uses hard `if harness == ...` branches and reads cleanly; an extension to `endswith` would introduce silent coupling between the chosen file extension and a downstream layout derivation. Explicit > implicit. Two extra lines, one in each function, both adjacent to the existing opencode/codex branches.

### Decision: gemini agent translator deferred to verify-time (Task 11)

The spec specifies an empirical check during build: link a toolkit-shipped agent into Gemini and confirm it round-trips through `/agents list`. If Gemini drops the raw symlink (analogous to how OpenCode dropped raw skills), we add `_translate_gemini_agent` before opening the PR. The default path is **no translator** (raw symlink); the verification step is Task 11.

---

## Task 1 — Register gemini in the support matrix (TDD)

**Files:**
- Modify: `src/agent_toolkit_cli/_support.py:19,24-58`
- Test: `tests/test_support.py:18-19,39-58`

- [ ] **Step 1.1: Update the canary tuple test in `tests/test_support.py:18-19`.**

Replace:

```python
def test_all_harnesses_is_canonical():
    assert ALL_HARNESSES == ("claude", "codex", "opencode", "pi")
```

with:

```python
def test_all_harnesses_is_canonical():
    assert ALL_HARNESSES == ("claude", "codex", "opencode", "gemini", "pi")
```

- [ ] **Step 1.2: Add `(gemini, *)` spot-checks. Below the existing `test_supported_pairs_known_members` (line 39-48), add:**

```python
def test_gemini_pairs_supported():
    """Gemini supports skill, agent, command, and (via adapter) mcp."""
    assert ("gemini", "skill") in SUPPORTED_PAIRS
    assert ("gemini", "agent") in SUPPORTED_PAIRS
    assert ("gemini", "command") in SUPPORTED_PAIRS
    # mcp is not in SUPPORTED_PAIRS — it's adapter-managed, not slot-projected.
    assert ("gemini", "mcp") not in SUPPORTED_PAIRS


def test_is_supported_gemini_kinds_at_both_scopes():
    assert is_supported("gemini", "skill", scope="user") is True
    assert is_supported("gemini", "skill", scope="project") is True
    assert is_supported("gemini", "agent", scope="user") is True
    assert is_supported("gemini", "agent", scope="project") is True
    assert is_supported("gemini", "command", scope="user") is True
    assert is_supported("gemini", "command", scope="project") is True
```

- [ ] **Step 1.3: Run tests to verify they fail.**

```bash
uv run pytest tests/test_support.py::test_all_harnesses_is_canonical tests/test_support.py::test_gemini_pairs_supported tests/test_support.py::test_is_supported_gemini_kinds_at_both_scopes -v
```

Expected: all three FAIL — `ALL_HARNESSES` still has 4 entries; `(gemini, *)` keys are absent.

- [ ] **Step 1.4: Update `ALL_HARNESSES` in `src/agent_toolkit_cli/_support.py:19`:**

Replace:

```python
ALL_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")
```

with:

```python
ALL_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "gemini", "pi")
```

- [ ] **Step 1.5: Add gemini rows to `_USER_TARGETS` in `src/agent_toolkit_cli/_support.py:24-38`. Insert these 3 rows between the existing `opencode` and `pi` blocks (preserve alphabetical-by-harness grouping):**

```python
    ("gemini", "skill"):       "{home}/.gemini/skills",
    ("gemini", "agent"):       "{home}/.gemini/agents",
    ("gemini", "command"):     "{home}/.gemini/commands",
```

- [ ] **Step 1.6: Add gemini rows to `_PROJECT_TARGETS` in `src/agent_toolkit_cli/_support.py:39-59`. Insert between `opencode` and `pi` blocks:**

```python
    ("gemini", "skill"):       ".gemini/skills",
    ("gemini", "agent"):       ".gemini/agents",
    ("gemini", "command"):     ".gemini/commands",
```

- [ ] **Step 1.7: Run the tests; they should now pass.**

```bash
uv run pytest tests/test_support.py -v
```

Expected: PASS for all new and existing tests in this file.

- [ ] **Step 1.8: Commit.**

```bash
git add src/agent_toolkit_cli/_support.py tests/test_support.py
git commit -m "feat(#53): register gemini in support matrix (skill, agent, command)"
```

---

## Task 2 — Wire HARNESS_HOMES so `harness_home_path('gemini')` works

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py:34-39`
- Test: `tests/test_link_lib.py` (new test)

- [ ] **Step 2.1: Add a failing test in `tests/test_link_lib.py`. Add at the end of the file:**

```python
def test_harness_home_path_gemini(monkeypatch, tmp_path):
    """harness_home_path returns ~/.gemini for gemini."""
    from agent_toolkit_cli.commands._link_lib import harness_home_path

    monkeypatch.setenv("HOME", str(tmp_path))
    assert harness_home_path("gemini") == tmp_path / ".gemini"
```

- [ ] **Step 2.2: Run; expect KeyError.**

```bash
uv run pytest tests/test_link_lib.py::test_harness_home_path_gemini -v
```

Expected: FAIL with `KeyError: 'gemini'`.

- [ ] **Step 2.3: Add `"gemini": ".gemini",` to `HARNESS_HOMES` in `src/agent_toolkit_cli/commands/_link_lib.py:34-39`:**

```python
HARNESS_HOMES: dict[str, str] = {
    "claude":   ".claude",
    "codex":    ".codex",
    "opencode": ".config/opencode",
    "gemini":   ".gemini",
    "pi":       ".pi",
}
```

- [ ] **Step 2.4: Run test; expect PASS.**

```bash
uv run pytest tests/test_link_lib.py::test_harness_home_path_gemini -v
```

- [ ] **Step 2.5: Commit.**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py tests/test_link_lib.py
git commit -m "feat(#53): add HARNESS_HOMES entry for gemini"
```

---

## Task 3 — Cache layout and slot-filename branches for `(gemini, command)`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py:65-126`
- Test: `tests/test_link_lib.py`

- [ ] **Step 3.1: Add failing tests in `tests/test_link_lib.py`:**

```python
def test_translated_slot_filename_gemini_command_uses_toml_extension():
    from agent_toolkit_cli.commands._link_lib import _translated_slot_filename

    assert _translated_slot_filename("hello", "command", "gemini") == "hello.toml"


def test_translate_slot_layout_gemini_command_is_file():
    from agent_toolkit_cli.commands._link_lib import _translate_slot_layout

    assert _translate_slot_layout("gemini", "command") == "file"


def test_scope_cache_root_gemini_user(monkeypatch, tmp_path):
    from agent_toolkit_cli.commands._link_lib import _scope_cache_root

    monkeypatch.setenv("HOME", str(tmp_path))
    root = _scope_cache_root("gemini", "user", project_root=tmp_path / "ignored")
    assert root == tmp_path / ".gemini" / ".agent-toolkit-cache"


def test_scope_cache_root_gemini_project(tmp_path):
    from agent_toolkit_cli.commands._link_lib import _scope_cache_root

    proj = tmp_path / "p"
    proj.mkdir()
    root = _scope_cache_root("gemini", "project", project_root=proj)
    assert root == proj / ".gemini" / ".agent-toolkit-cache"
```

- [ ] **Step 3.2: Run tests; expect failures.**

```bash
uv run pytest tests/test_link_lib.py::test_translated_slot_filename_gemini_command_uses_toml_extension tests/test_link_lib.py::test_translate_slot_layout_gemini_command_is_file tests/test_link_lib.py::test_scope_cache_root_gemini_user tests/test_link_lib.py::test_scope_cache_root_gemini_project -v
```

Expected: layout tests fail (`ValueError: no cache layout defined for harness 'gemini'`); filename test currently returns bare `"hello"`; slot-layout test currently returns `"dir-symlink"`.

- [ ] **Step 3.3: Extend `_CACHE_LAYOUT` in `src/agent_toolkit_cli/commands/_link_lib.py:65-74`. Add a gemini block:**

```python
_CACHE_LAYOUT: dict[str, dict[str, tuple[str, ...]]] = {
    "opencode": {
        "user":    (".config", "opencode", CACHE_DIR_NAME),
        "project": (".opencode", CACHE_DIR_NAME),
    },
    "codex": {
        "user":    (".codex", CACHE_DIR_NAME),
        "project": (".codex", CACHE_DIR_NAME),
    },
    "gemini": {
        "user":    (".gemini", CACHE_DIR_NAME),
        "project": (".gemini", CACHE_DIR_NAME),
    },
}
```

- [ ] **Step 3.4: Extend `_translated_slot_filename` in `src/agent_toolkit_cli/commands/_link_lib.py:96-107`. Insert the gemini branch *before* the opencode branch (hard-branch style, explicit):**

```python
def _translated_slot_filename(slug: str, kind: str, harness: str) -> str:
    """Return the filename used for the slot symlink in this (harness, kind).

    File-slot kinds get an extension matching the harness:
      - opencode agents/commands → `<slug>.md`
      - gemini commands → `<slug>.toml`
    Directory-slot kinds — and any unsupported pair — get the bare `<slug>`.

    Callers can detect the slot shape from the result: any extension ⇒
    file-slot; otherwise directory-slot or non-translated.
    """
    if harness == "gemini" and kind == "command":
        return f"{slug}.toml"
    if harness == "opencode" and kind in {"agent", "command"}:
        return f"{slug}.md"
    return slug
```

- [ ] **Step 3.5: Extend `_translate_slot_layout` in `src/agent_toolkit_cli/commands/_link_lib.py:121-126`. Add a gemini-command hard-branch:**

```python
def _translate_slot_layout(harness: str, kind: str) -> str:
    if harness == "opencode" and kind == "skill":
        return "dir-with-file-symlink"
    if harness == "gemini" and kind == "command":
        return "file"
    if _translated_slot_filename("x", kind, harness).endswith(".md"):
        return "file"
    return "dir-symlink"
```

- [ ] **Step 3.6: Run tests; expect PASS.**

```bash
uv run pytest tests/test_link_lib.py -v
```

- [ ] **Step 3.7: Commit.**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py tests/test_link_lib.py
git commit -m "feat(#53): cache layout and TOML slot for gemini commands"
```

---

## Task 4 — TOML translator for `(gemini, command)`

**Files:**
- Modify: `src/agent_toolkit_cli/_translators.py:103-108`
- Test: `tests/test_translators.py`

- [ ] **Step 4.1: Add failing tests. In `tests/test_translators.py` (look near existing translator tests; if file doesn't yet have tests for opencode/codex translators, scan the file to find the test style and match it). Add:**

```python
def test_translate_gemini_command_minimum(tmp_path):
    """Minimum: description + prompt, no spec block."""
    import tomllib
    from agent_toolkit_cli.walker import AssetRecord
    from agent_toolkit_cli._translators import _translate_gemini_command

    record = AssetRecord(
        path=tmp_path / "noop.md",
        kind="command",
        slug="noop",
        metadata={
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "noop", "description": "Do nothing."},
        },
    )
    body = "Just chill.\n"
    out = _translate_gemini_command(record, body)
    parsed = tomllib.loads(out.decode("utf-8"))
    assert parsed["description"] == "Do nothing."
    assert parsed["prompt"].strip() == "Just chill."
    assert "agent_toolkit_cli" in parsed
    assert parsed["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"


def test_translate_gemini_command_round_trips_wrapper(tmp_path):
    """metadata + spec encoded as JSON strings under [agent_toolkit_cli]."""
    import json
    import tomllib
    from agent_toolkit_cli.walker import AssetRecord
    from agent_toolkit_cli._translators import _translate_gemini_command

    md = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {"name": "n", "description": "d", "tags": ["a", "b"]},
        "spec": {"harnesses": ["gemini"]},
    }
    record = AssetRecord(
        path=tmp_path / "n.md", kind="command", slug="n", metadata=md,
    )
    out = _translate_gemini_command(record, "body\n")
    parsed = tomllib.loads(out.decode("utf-8"))
    wrapper = parsed["agent_toolkit_cli"]
    assert wrapper["apiVersion"] == "agent-toolkit/v1alpha2"
    assert json.loads(wrapper["metadata"]) == md["metadata"]
    assert json.loads(wrapper["spec"]) == md["spec"]


def test_translate_gemini_command_handles_triple_quoted_body(tmp_path):
    """Bodies containing triple-quotes must round-trip safely."""
    import tomllib
    from agent_toolkit_cli.walker import AssetRecord
    from agent_toolkit_cli._translators import _translate_gemini_command

    record = AssetRecord(
        path=tmp_path / "q.md", kind="command", slug="q",
        metadata={"apiVersion": "agent-toolkit/v1alpha2",
                  "metadata": {"name": "q", "description": "d"}},
    )
    body = 'before """ in middle """ end\n'
    out = _translate_gemini_command(record, body)
    parsed = tomllib.loads(out.decode("utf-8"))
    assert parsed["prompt"] == body
```

Note on `AssetRecord` shape: confirm by reading `src/agent_toolkit_cli/walker.py`. If the dataclass fields differ from `(path, kind, slug, metadata)`, adjust the test constructor accordingly. The translator only reads `record.metadata`, so the test passes any object with that attribute — a `SimpleNamespace` is acceptable if `AssetRecord` is strict.

- [ ] **Step 4.2: Run tests; expect import-error for `_translate_gemini_command`.**

```bash
uv run pytest tests/test_translators.py -k gemini -v
```

Expected: FAIL with `cannot import name '_translate_gemini_command'`.

- [ ] **Step 4.3: Implement `_translate_gemini_command` in `src/agent_toolkit_cli/_translators.py`. Add this function after `_translate_opencode_skill` (line 100) and before the `TRANSLATORS` dict:**

```python
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
    import json

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
    # Then break any internal `\"\"\"` by escaping the third quote.
    escaped = escaped.replace('"""', '""\\"')
    return f'"""\n{escaped}"""'
```

- [ ] **Step 4.4: Register `_translate_gemini_command` in the `TRANSLATORS` dict at the bottom of `src/agent_toolkit_cli/_translators.py:103-108`:**

```python
TRANSLATORS: dict[tuple[str, str], Callable[[AssetRecord, str], bytes]] = {
    ("opencode", "agent"): _translate_opencode_agent,
    ("opencode", "command"): _translate_opencode_command,
    ("codex", "skill"): _translate_codex_skill,
    ("opencode", "skill"): _translate_opencode_skill,
    ("gemini", "command"): _translate_gemini_command,
}
```

- [ ] **Step 4.5: Run tests; expect PASS.**

```bash
uv run pytest tests/test_translators.py -k gemini -v
```

- [ ] **Step 4.6: Commit.**

```bash
git add src/agent_toolkit_cli/_translators.py tests/test_translators.py
git commit -m "feat(#53): TOML translator for (gemini, command)"
```

---

## Task 5 — Gemini MCP adapter (`harness_adapters/gemini.py`)

**Files:**
- Create: `src/agent_toolkit_cli/harness_adapters/gemini.py`
- Modify: `src/agent_toolkit_cli/harness_adapters/__init__.py:21,24-49`
- Test: `tests/test_mcp_adapters_gemini.py` (new)

- [ ] **Step 5.1: Create the new test file `tests/test_mcp_adapters_gemini.py`. Mirror `tests/test_mcp_adapters_opencode.py`'s shape but use the Claude-style on-disk shape (`mcpServers` key; `type: stdio|sse|http`):**

```python
"""Gemini adapter — ConfigFileAdapter against ~/.gemini/settings.json."""
from __future__ import annotations

import json

import pytest


def _make_entry(name: str = "context7", *, transport: str = "stdio",
                command: str = "npx", args: list[str] | None = None,
                env: dict[str, str] | None = None,
                url: str | None = None,
                headers: dict[str, str] | None = None):
    from agent_toolkit_cli.harness_adapters.base import McpEntry

    inner: dict = {"command": command}
    if args is not None:
        inner["args"] = args
    if env is not None:
        inner["env"] = env

    spec: dict = {"transport": transport, "install_method": "npx"}
    if url is not None:
        spec["url"] = url
    if headers is not None:
        spec["headers"] = headers

    return McpEntry(name=name, inner_config=inner, mcp_spec=spec)


def test_gemini_adapter_basic_attrs():
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    a = GeminiAdapter()
    assert a.name == "gemini"
    assert a.strategy == "config_file"


def test_gemini_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".gemini" / "settings.json"


def test_gemini_project_config_target_requires_dir(tmp_path):
    """Project target only set when .gemini/ exists in project_root."""
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = GeminiAdapter()
    assert a.config_target("project", proj) is None
    (proj / ".gemini").mkdir()
    assert a.config_target("project", proj) == proj / ".gemini" / "settings.json"


def test_gemini_can_install_accepts_all_transports():
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    a = GeminiAdapter()
    a.can_install(_make_entry(transport="stdio"))
    a.can_install(_make_entry(transport="http", url="https://x"))
    a.can_install(_make_entry(transport="sse", url="https://x"))


def test_gemini_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """stdio entry → settings.json with top-level mcpServers.<name>."""
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"], env={"TOK": "x"})

    [act] = a.diff("user", tmp_path, [entry])
    assert act.op == "create"
    assert act.path == tmp_path / ".gemini" / "settings.json"
    parsed = json.loads(act.contents)
    assert "mcpServers" in parsed
    server = parsed["mcpServers"]["context7"]
    assert server["type"] == "stdio"
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "@upstash/context7-mcp"]
    assert server["env"] == {"TOK": "x"}


def test_gemini_diff_remote_shape_for_http(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    entry = _make_entry(transport="http", url="https://example/mcp",
                        headers={"Authorization": "Bearer x"})
    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    server = parsed["mcpServers"]["context7"]
    assert server["type"] == "http"
    assert server["url"] == "https://example/mcp"
    assert server["headers"] == {"Authorization": "Bearer x"}


def test_gemini_list_installed_round_trips(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".gemini" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"mcpServers": {"a": {}, "b": {}}}))
    a = GeminiAdapter()
    assert a.list_installed("user", tmp_path) == {"a", "b"}


def test_gemini_entry_drift_detects_change(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    entry = _make_entry()

    # Pre-write a divergent on-disk entry
    settings = tmp_path / ".gemini" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"mcpServers": {"context7": {"type": "stdio",
                                                                "command": "DIFFERENT"}}}))
    assert a.entry_drift("user", tmp_path, entry) is True


def test_gemini_missing_file_returns_empty(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    assert a.list_installed("user", tmp_path) == set()
    assert a.entry_drift("user", tmp_path, _make_entry()) is False


def test_gemini_get_adapter_returns_real_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    a = get_adapter("gemini", "mcp")
    assert isinstance(a, GeminiAdapter)
    assert not isinstance(a, UnimplementedAdapter)
```

- [ ] **Step 5.2: Run tests; expect import-error.**

```bash
uv run pytest tests/test_mcp_adapters_gemini.py -v
```

Expected: collection error — module `agent_toolkit_cli.harness_adapters.gemini` does not exist.

- [ ] **Step 5.3: Create `src/agent_toolkit_cli/harness_adapters/gemini.py`. Modelled on `claude.py` (camelCase `mcpServers`, JSON file, no transport refusal):**

```python
"""Gemini MCP adapter — ConfigFileAdapter against ~/.gemini/settings.json.

Round-trip via stdlib json. Managed namespace: top-level `mcpServers.<name>`.

Ownership rule (manage by name; same as claude/codex/opencode): we own every
name in `previously_allowed | {e.name for e in entries}`. On-disk entries
whose names fall outside that union are hand-rolled and preserved verbatim.

No transport refusal — Gemini's MCP loader supports stdio, sse, http natively
(verified against Gemini CLI v0.39 docs). The adapter maps
`mcp_spec.transport` to the on-disk `type` field. The Gemini on-disk shape
mirrors Claude's: `{"type": "stdio", "command", "args"?, "env"?}` for stdio,
`{"type": "sse"|"http", "url", "headers"?}` for remote transports.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    WriteAction,
)


class GeminiAdapter:
    name: str = "gemini"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".gemini" / "settings.json"
        gemini_dir = project_root / ".gemini"
        if not gemini_dir.is_dir():
            return None
        return gemini_dir / "settings.json"

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        return None

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        servers = doc.get("mcpServers")
        if not isinstance(servers, dict):
            return set()
        return set(servers.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        doc = self._read(target)
        servers = doc.get("mcpServers") or {}
        on_disk = servers.get(entry.name)
        if on_disk is None:
            return False
        return on_disk != self._build_entry_dict(entry)

    # ---- diff (the engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[McpEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        target = self.config_target(scope, project_root)
        if target is None:
            return []
        desired_names = {e.name for e in entries}
        managed_names = set(previously_allowed) | desired_names

        if not target.is_file():
            doc: dict = {}
            self._merge_entries(doc, entries,
                                managed_names=managed_names,
                                desired_names=desired_names)
            rendered = self._dump(doc)
            if not rendered or rendered == b"{}\n":
                return []
            return [WriteAction(
                path=target, op="create",
                bytes_before=None, bytes_after=len(rendered),
                contents=rendered,
            )]

        before_bytes = target.read_bytes()
        doc = self._read(target)
        self._merge_entries(doc, entries,
                            managed_names=managed_names,
                            desired_names=desired_names)
        after_bytes = self._dump(doc)
        if after_bytes == before_bytes:
            return []
        return [WriteAction(
            path=target, op="update",
            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
            contents=after_bytes,
        )]

    # ---- helpers ----
    @staticmethod
    def _read(path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)

    @staticmethod
    def _dump(doc: dict) -> bytes:
        return (
            json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")

    def _merge_entries(
        self,
        doc: dict,
        entries: list[McpEntry],
        *,
        managed_names: set[str],
        desired_names: set[str],
    ) -> None:
        servers = doc.get("mcpServers")
        if servers is None and not entries:
            return

        if "mcpServers" not in doc:
            doc["mcpServers"] = {}
        servers = doc["mcpServers"]

        for name in list(servers.keys()):
            if name in managed_names and name not in desired_names:
                del servers[name]

        for entry in sorted(entries, key=lambda e: e.name):
            servers[entry.name] = self._build_entry_dict(entry)

        if not doc["mcpServers"]:
            del doc["mcpServers"]

    @staticmethod
    def _build_entry_dict(entry: McpEntry) -> dict:
        cfg = entry.inner_config or {}
        spec = entry.mcp_spec or {}
        transport = spec.get("transport") or "stdio"

        if transport in ("sse", "http"):
            url = spec.get("url")
            if not url:
                raise CannotInstall(
                    f"{entry.name}: spec.mcp.url required for transport={transport!r}"
                )
            out: dict = {"type": transport, "url": url}
            headers = spec.get("headers")
            if headers:
                out["headers"] = {str(k): str(v) for k, v in headers.items()}
            return out

        # stdio
        cmd = cfg.get("command")
        if cmd is None:
            raise CannotInstall(
                f"{entry.name}: inner_config.command missing — required for stdio"
            )
        out = {"type": "stdio", "command": cmd}
        if cfg.get("args"):
            out["args"] = list(cfg["args"])
        if cfg.get("env"):
            env_dict = cfg["env"]
            if not isinstance(env_dict, dict):
                raise CannotInstall(
                    f"{entry.name}: inner_config.env must be a dict, "
                    f"got {type(env_dict).__name__}"
                )
            out["env"] = {str(k): str(v) for k, v in env_dict.items()}
        return out
```

- [ ] **Step 5.4: Wire the adapter into the registry. In `src/agent_toolkit_cli/harness_adapters/__init__.py:21`, change:**

```python
_KNOWN_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")
```

to:

```python
_KNOWN_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "gemini", "pi")
```

And in `get_adapter` (line 24-49), add this branch *before* the final `return UnimplementedAdapter(harness)`:

```python
    if harness == "gemini" and kind == "mcp":
        from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter
        return GeminiAdapter()
```

- [ ] **Step 5.5: Run new tests; expect PASS.**

```bash
uv run pytest tests/test_mcp_adapters_gemini.py -v
```

- [ ] **Step 5.6: Run the whole test suite to catch any unrelated regressions.**

```bash
uv run pytest -q
```

Expected: all green. If anything else broke, that's a real regression — investigate before commit.

- [ ] **Step 5.7: Commit.**

```bash
git add src/agent_toolkit_cli/harness_adapters/gemini.py src/agent_toolkit_cli/harness_adapters/__init__.py tests/test_mcp_adapters_gemini.py
git commit -m "feat(#53): real ConfigFileAdapter for gemini MCP (settings.json/mcpServers)"
```

---

## Task 6 — Doctor harness_homes summary

**Files:**
- Modify: `src/agent_toolkit_cli/doctor/harness_homes.py:33`

- [ ] **Step 6.1: Find existing test, if any, that asserts the doctor summary string. Grep:**

```bash
grep -rn "harness homes present" tests/ src/ || true
grep -rn "all 4 harness" tests/ src/ || true
```

If a test exists, update its expected string. If not, skip the test and rely on the fact that `len(ALL_HARNESSES) == 5` after Task 1.

- [ ] **Step 6.2: Replace the hardcoded "4" in `src/agent_toolkit_cli/doctor/harness_homes.py:33`. Change:**

```python
        summary="all 4 harness homes present",
```

to:

```python
        summary=f"all {len(ALL_HARNESSES)} harness homes present",
```

- [ ] **Step 6.3: Run any doctor tests:**

```bash
uv run pytest tests/ -k "harness_home" -v
```

- [ ] **Step 6.4: Commit.**

```bash
git add src/agent_toolkit_cli/doctor/harness_homes.py
git commit -m "feat(#53): derive doctor harness_homes summary from ALL_HARNESSES"
```

---

## Task 7 — Update the harness-matrix doc and its parser test

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md`
- Modify: `tests/test_harness_matrix.py:51-60,318-320`

- [ ] **Step 7.1: Update the regex first (so the parity test runs against the new column count). In `tests/test_harness_matrix.py:51`, change:**

```python
_HARNESS_ORDER = ("claude", "codex", "opencode", "pi")
```

to:

```python
_HARNESS_ORDER = ("claude", "codex", "opencode", "gemini", "pi")
```

- [ ] **Step 7.2: Extend `_ROW_RE` in `tests/test_harness_matrix.py:54-60`. Insert a `gemini` named group *before* the `pi` group (mirroring the column order):**

```python
_ROW_RE = re.compile(
    r"^\|\s*\*\*(?P<kind>[a-z][a-z0-9-]*)\*\*\s*\|"
    r"(?P<claude>[^|]+)\|"
    r"(?P<codex>[^|]+)\|"
    r"(?P<opencode>[^|]+)\|"
    r"(?P<gemini>[^|]+)\|"
    r"(?P<pi>[^|]+)\|"
)
```

- [ ] **Step 7.3: Extend `_TRANSLATE_PATH_RE` in `tests/test_harness_matrix.py:318-320` to accept `commands/<slug>.toml`:**

Change:

```python
_TRANSLATE_PATH_RE = re.compile(
    r"(agents/<slug>\.md|commands/<slug>\.md|skills/<slug>/SKILL\.md)\s*$"
)
```

to:

```python
_TRANSLATE_PATH_RE = re.compile(
    r"(agents/<slug>\.md|commands/<slug>\.md|commands/<slug>\.toml|"
    r"skills/<slug>/SKILL\.md)\s*$"
)
```

- [ ] **Step 7.4: Run the parity test; expect FAIL because the doc still has 4 columns.**

```bash
uv run pytest tests/test_harness_matrix.py -v
```

Expected: failures about missing Gemini in matrix; potentially also "all_harnesses_covered" assertion fires.

- [ ] **Step 7.5: Update `docs/agent-toolkit/harness-matrix.md`. Find the matrix table header (line 60):**

Change:

```markdown
| Kind \\ Harness | Claude | Codex | OpenCode | Pi |
|---|---|---|---|---|
```

to:

```markdown
| Kind \\ Harness | Claude | Codex | OpenCode | Gemini | Pi |
|---|---|---|---|---|---|
```

- [ ] **Step 7.6: For each existing row (skill, agent, command, hook, plugin, mcp, pi-extension), insert a Gemini cell between the OpenCode cell and the Pi cell. Cell contents:**

| Kind | Gemini cell |
|---|---|
| **skill** | `symlink → ~/.gemini/skills/<slug>/` |
| **agent** | `symlink → ~/.gemini/agents/<slug>.md` |
| **command** | `translate → ~/.gemini/commands/<slug>.toml (cache: ~/.gemini/.agent-toolkit-cache/command/<slug>.toml) — emits Gemini TOML schema (description + prompt) plus a `[agent_toolkit_cli]` table with JSON-encoded wrapper for round-trip traceability` |
| **hook** | `unsupported (by design) — Gemini hooks are shell-script entries under .gemini/hooks/ keyed by stdin/exit-code, not toolkit drop-in markdown` |
| **plugin** | `unsupported (by design) — Gemini extends via "extensions" (npm-installed packages with gemini-extension.json), not markdown plugins` |
| **mcp** | `config_file → ~/.gemini/settings.json mcpServers.<name> (camelCase; same JSON shape as Claude — type discriminator stdio\|sse\|http)` |
| **pi-extension** | `unsupported (by design)` |

The exact text matters because `_ROW_RE` parses on `|` boundaries and `_cell_mechanism` checks the leading keyword. Mechanism keywords must appear at the start of each cell, lowercase, as listed in `VALID_MECHANISMS`.

- [ ] **Step 7.7: Refresh the "Why some pairs are by-design unsupported" prose section (line 122 onwards) to mention Gemini briefly under `hook` and `plugin`. Two-sentence additions only — the existing prose handles the other harnesses fine. Keep it tight: one bullet per gemini-specific clarification.**

Add to the **hook** section:

```markdown
  - **By design** for Gemini: Gemini's hooks are shell scripts keyed by event in `~/.gemini/hooks/`, configured via stdin/exit-code semantics, not toolkit-shape markdown.
```

Add to the **plugin** section:

```markdown
  - Gemini: extends via "extensions" — npm-installed packages with `gemini-extension.json` manifests, not markdown plugins. Different install verb, different shape.
```

Add to the **mcp** section:

```markdown
- **mcp** is supported on four of five harnesses (claude, codex, opencode, gemini) via `config_file` adapters. Gemini stores entries in `~/.gemini/settings.json` under `mcpServers` (camelCase, same shape as Claude). Pi has no MCP concept — it loads tools from its own extension API instead.
```

(replacing the existing "three of four" paragraph)

- [ ] **Step 7.8: Run the parity test; expect PASS.**

```bash
uv run pytest tests/test_harness_matrix.py -v
```

Expected: all green. If a cell fails the `_cell_mechanism` check, the leading keyword in that cell isn't in `VALID_MECHANISMS` — fix the cell.

- [ ] **Step 7.9: Commit.**

```bash
git add docs/agent-toolkit/harness-matrix.md tests/test_harness_matrix.py
git commit -m "docs(#53): harness-matrix.md gains Gemini column at full parity"
```

---

## Task 8 — README

**Files:**
- Modify: `README.md:3,55`

- [ ] **Step 8.1: Update the harness list in `README.md:3`. Change:**

```markdown
Bash + Python CLI and Textual TUI for managing the [`agent-toolkit`](https://github.com/ajanderson1/agent-toolkit) asset library across Claude Code, Codex, OpenCode, and Pi.
```

to:

```markdown
Bash + Python CLI and Textual TUI for managing the [`agent-toolkit`](https://github.com/ajanderson1/agent-toolkit) asset library across Claude Code, Codex, OpenCode, Gemini CLI, and Pi.
```

- [ ] **Step 8.2: Update the MCP status note at `README.md:55`. The current text says "Codex shipped; Claude / OpenCode / Pi pending follow-up PRs." Claude and OpenCode have shipped since (see `harness_adapters/claude.py` and `opencode.py`). Replace with:**

```markdown
**MCPs** (Claude, Codex, OpenCode, and Gemini shipped via `config_file` adapters; Pi has no MCP concept — see harness-matrix.md).
```

- [ ] **Step 8.3: Commit.**

```bash
git add README.md
git commit -m "docs(#53): README mentions Gemini CLI; refresh MCP-status note"
```

---

## Task 9 — Full test sweep + repo-level smoke

**Files:** none — verification only.

- [ ] **Step 9.1: Full pytest run.**

```bash
uv run pytest -q
```

Expected: all tests pass. If a test outside the gemini change fails, investigate — likely a missing branch somewhere that enumerates `ALL_HARNESSES`.

- [ ] **Step 9.2: Lint.**

```bash
uv run ruff check src tests
```

Expected: no findings.

- [ ] **Step 9.3: Schema check (pre-commit hook does this; re-run for parity).**

```bash
uv run python scripts/schema_vendor_check.py 2>/dev/null || echo "no schema check script — skip if not present"
```

- [ ] **Step 9.4: CLI smoke (no commit; just observe).**

```bash
uv run agent-toolkit-cli doctor --group harness-homes
uv run agent-toolkit-cli list skill gemini || true
uv run agent-toolkit-cli list command gemini || true
```

Expected: `doctor` reports 5 harness homes (`gemini` listed; may say "not present" depending on the test machine — that's a WARN, not a failure). `list` does not crash; it may report no installed assets, which is fine.

- [ ] **Step 9.5: If any failures, fix them in their own commit before proceeding.**

---

## Task 10 — Empirical verification: link a toolkit asset into Gemini

**Files:** none — runtime verification.

This is the spec's "verify-time decision" for whether `(gemini, agent)` and `(gemini, command)` need a translator beyond what we've built. Output goes to `assets/verification/53/`.

- [ ] **Step 10.1: Create a transient project root for the experiment.**

```bash
EXP=$(mktemp -d)
cd "$EXP"
git init -q
mkdir -p .gemini
```

- [ ] **Step 10.2: Walk through `link project gemini` for one of each kind. Use any toolkit-shipped asset (e.g. `agent:code-reviewer`, `command:agent-toolkit-help`, `skill:some-skill`). If the local agent-toolkit clone is at `~/GitHub/agent-toolkit`, use `--toolkit-repo` to point at it; otherwise let the four-step resolution find it.**

For each kind:

```bash
# Replace <slug> with a real one from `agent-toolkit-cli inventory`.
uv run agent-toolkit-cli link project gemini agent:<slug>  --project "$EXP" -y
uv run agent-toolkit-cli link project gemini command:<slug> --project "$EXP" -y
uv run agent-toolkit-cli link project gemini skill:<slug>   --project "$EXP" -y
```

Verify the slot files / directories exist with the expected shape:

```bash
ls -la "$EXP/.gemini/agents/"      # expect <slug>.md as a symlink
ls -la "$EXP/.gemini/commands/"    # expect <slug>.toml as a symlink (to cache)
ls -la "$EXP/.gemini/skills/"      # expect <slug>/ as a directory symlink
cat "$EXP/.gemini/commands/<slug>.toml"  # expect valid TOML
```

- [ ] **Step 10.3: Validate the cache TOML parses.**

```bash
python -c "import tomllib, sys; tomllib.loads(open(sys.argv[1]).read())" "$EXP/.gemini/commands/<slug>.toml"
```

Expected: exit 0, no traceback.

- [ ] **Step 10.4: If Gemini CLI is installed on the box, perform the runtime round-trip check.**

```bash
which gemini && cd "$EXP" && gemini --help 2>&1 | head -20
# Then in a separate manual session: cd "$EXP" && gemini
#   inside: /agents list   → expect the linked agent to appear
#   inside: /<slug>          → expect the linked command to run
```

This step is **observational, not blocking**. If Gemini drops the raw agent symlink, capture the symptom (which kind, what error, expected vs actual frontmatter), then return to Task 4 / a new task to add `_translate_gemini_agent`. If everything appears, copy the terminal transcript to `assets/verification/53/gemini-link-roundtrip.txt`.

- [ ] **Step 10.5: Tear down the experiment.**

```bash
cd /  # leave the tmp dir
rm -rf "$EXP"
```

- [ ] **Step 10.6: Note the result in the flow.log** (this is verification, not a commit):

```bash
echo "[$(date +%H:%M:%S)] Task 10: empirical link round-trip — <PASS|FAIL details>" >> assets/verification/53/flow.log
```

If FAIL: that becomes Task 11. If PASS: skip Task 11.

---

## Task 11 (conditional) — Add `_translate_gemini_agent` if verification fails

Only run this task if Task 10's runtime check showed Gemini silently dropping the raw markdown agent. Otherwise skip.

**Files:**
- Modify: `src/agent_toolkit_cli/_translators.py`
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py` (for the slot filename, if needed)
- Modify: `tests/test_translators.py`
- Modify: `docs/agent-toolkit/harness-matrix.md` (change the agent row from `symlink` to `translate`)

- [ ] **Step 11.1: From Task 10's symptom, determine the required frontmatter fields. Document them in the translator docstring with a "verified against Gemini CLI v<version>" attribution, mirroring `_translate_opencode_skill`'s docstring.**

- [ ] **Step 11.2: Implement `_translate_gemini_agent(record, body) -> bytes`** following the YAML-frontmatter pattern from `_translate_opencode_agent`. The translator emits markdown — no TOML conversion — because Gemini agents are `.md` files per docs.

- [ ] **Step 11.3: Register in `TRANSLATORS`:**

```python
("gemini", "agent"): _translate_gemini_agent,
```

- [ ] **Step 11.4: Update the matrix cell** (Task 7's table row) from `symlink → ...` to `translate → ...` with the cache path.

- [ ] **Step 11.5: Add a translator unit test and rerun the link round-trip from Task 10.**

- [ ] **Step 11.6: Commit.**

```bash
git add src/agent_toolkit_cli/_translators.py tests/test_translators.py docs/agent-toolkit/harness-matrix.md
git commit -m "feat(#53): translator for (gemini, agent) — Gemini requires <field> in frontmatter"
```

---

## Self-Review

Running the writing-plans self-review checklist against the spec and this plan.

### 1. Spec coverage

Mapping spec acceptance criteria to tasks:

| Spec ack | Covered by |
|---|---|
| `gemini` in `ALL_HARNESSES` | Task 1.4 |
| `gemini` in `_KNOWN_HARNESSES` | Task 5.4 |
| User-scope path entries for 4 kinds | Task 1.5 (skill/agent/command), Task 5.3 (mcp via adapter, not _USER_TARGETS) |
| Project-scope path entries | Task 1.6 |
| `list`, `link`, `doctor`, translator dispatch recognise `gemini` | Tasks 1+2+5 cover the registries; Task 9.4 smoke-tests the CLI commands |
| `harness_adapters/gemini.py` exists as a real adapter | Task 5.3 |
| Test coverage updated | Tasks 1.1-1.2, 2.1, 3.1, 4.1, 5.1, 7.1-7.3 |
| README / docs updated | Tasks 7, 8 |
| Empirical agent-translator check | Task 10 (and conditional Task 11) |
| TOML translator for `(gemini, command)` | Task 4 |
| `_translated_slot_filename` and `_translate_slot_layout` handle TOML | Task 3 |
| `_TRANSLATE_PATH_RE` allows `commands/<slug>.toml` | Task 7.3 |

No gaps.

### 2. Placeholder scan

Searched for the bad phrases listed in writing-plans:
- "TBD" / "TODO" / "implement later" — none
- "Add appropriate error handling" / "handle edge cases" — none
- "Write tests for the above" (without code) — every test step shows actual test code
- "Similar to Task N" — none; code is repeated where needed

Task 10 step 10.2 uses `<slug>` placeholders — those are intentional CLI command templates (the engineer fills them with an actual asset slug from the live inventory). That is operational, not a planning placeholder.

### 3. Type / name consistency

- Adapter class name: `GeminiAdapter` (Task 5.1 test, Task 5.3 implementation, Task 5.4 registry) — consistent.
- Translator function name: `_translate_gemini_command` (Task 4.1, 4.3, 4.4) — consistent.
- Module path: `agent_toolkit_cli.harness_adapters.gemini` (Task 5.1, 5.3, 5.4) — consistent.
- Tuple order: `("claude", "codex", "opencode", "gemini", "pi")` everywhere (Task 1.1, 1.4, 5.4, 7.1) — consistent.

No mismatches.

### 4. Discrepancy with `_USER_TARGETS` for MCP

Spec acceptance criterion says "User-scope and project-scope path entries exist in `_support.py` for the resource kinds Gemini supports". MCP is not in `_USER_TARGETS` because it's adapter-managed, not slot-projected — this matches how Claude/Codex/OpenCode MCP rows are absent from `_USER_TARGETS`. Task 1.2's `test_gemini_pairs_supported` makes this explicit (`("gemini", "mcp") not in SUPPORTED_PAIRS`). Aligned with existing pattern.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-add-gemini-cli-to-supported-harnesses.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
