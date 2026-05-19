# Add Gemini CLI to supported harnesses — design

**Issue:** #53
**Branch:** `feat/53-add-gemini-cli-to-supported-harnesses`
**Date:** 2026-05-19
**Mode:** `--guided`

## Goal

Add `gemini` (Gemini CLI) as the fifth supported harness in agent-toolkit-cli, at full parity with `claude` for the four resource kinds the toolkit manages: `skill`, `agent`, `command`, `mcp`. After this PR, `agent-toolkit list/link/doctor` and the translator dispatch must recognise `gemini` end-to-end, with no `UnimplementedAdapter` placeholder for MCP — Gemini's MCP support is live today via `~/.gemini/settings.json` → `mcpServers`, so we ship a real `ConfigFileAdapter`.

## Non-goals

- Reworking the harness portability rules in `~/.conventions/conventions/agents-md.md` (out of scope per issue).
- Refactoring the translator infra beyond the small additions needed for `.toml` cache files.
- Supporting Gemini CLI features the toolkit does not yet model (hooks, extensions, plan mode artifacts).

## Reference: Gemini CLI conventions (verified against official docs)

| Kind | User scope | Project scope | Discovery mechanism |
|---|---|---|---|
| skill | `~/.gemini/skills/<name>/` (dir, contains `SKILL.md` + bundled resources) | `<root>/.gemini/skills/<name>/` | Auto-discovered at session start |
| agent | `~/.gemini/agents/<name>.md` (markdown with YAML frontmatter) | `<root>/.gemini/agents/<name>.md` | `/agents list` registry |
| command | `~/.gemini/commands/<name>.toml` (TOML; nesting allowed for namespacing) | `<root>/.gemini/commands/<name>.toml` | Auto-discovered; invoked via `/<name>` |
| mcp | `~/.gemini/settings.json` → top-level key `mcpServers` (camelCase) | `<root>/.gemini/settings.json` → `mcpServers` | Loaded at session start |

Project-scope home is `.gemini/` in the project root — mirrors the Claude pattern.

## Architecture

### 1. Registry surface (`_support.py`)

- Insert `"gemini"` into `ALL_HARNESSES` **before `pi`** (tuple order: `claude, codex, opencode, gemini, pi`). The canary assertion in `tests/test_support.py:19` is updated to match. Rationale: gemini ships with a real MCP adapter; pi remains the placeholder-only harness, so it stays at the end of the tuple.
- Add four entries to `_USER_TARGETS` and four to `_PROJECT_TARGETS`, per the table above. Use `Path("...")` literals consistent with neighbouring rows.
- No changes to `_USER_TARGET_ALIASES` / `_PROJECT_TARGET_ALIASES` unless an alias is required for backward compat (none expected for a new harness).

### 2. Adapter registry (`harness_adapters/__init__.py`)

- Insert `"gemini"` into `_KNOWN_HARNESSES` before `pi` (mirror the `ALL_HARNESSES` order).
- Add a branch in `get_adapter` alongside `claude` and `codex` (real adapters), **not** the `pi`/fallthrough path. Returns an instance of the `ConfigFileAdapter` defined in `harness_adapters/gemini.py`.

### 3. MCP adapter (`harness_adapters/gemini.py` — new)

- Follows the existing `ConfigFileAdapter` protocol from `harness_adapters/base.py`.
- `config_target(scope, project_root)`:
  - user scope → `~/.gemini/settings.json`
  - project scope → `<project_root>/.gemini/settings.json`
- Top-level key: `mcpServers` (camelCase). Same nesting shape as Claude's `~/.claude.json`.
- `can_install(entry)`: accept stdio (`command` + `args`) and HTTP/SSE (`url`) entries. Gemini supports both per docs.
- `list_installed`, `entry_drift`, `diff`: standard `ConfigFileAdapter` implementations, modelled on the Claude adapter — not OpenCode's (OpenCode uses different key `mcp` and a `type: local|remote` discriminator).
- Empty file / missing file: same protocol semantics as the Claude adapter.

### 4. Translators (`_translators.py`)

#### `(gemini, command)` — TOML emitter

A new translator `_translate_gemini_command(record, body) -> bytes`. Output:

```toml
description = "<metadata.description from frontmatter>"
prompt = """
<verbatim markdown body>
"""

[agent_toolkit_cli]
apiVersion = "<wrapper apiVersion>"
metadata = "<JSON-encoded metadata block>"
spec = "<JSON-encoded spec block, omitted if absent>"
```

Rationale for the JSON-string wrapper fields: TOML cannot cleanly represent the toolkit's free-form `metadata`/`spec` blocks (lists of dicts, mixed types). Encoding them as JSON strings under the `[agent_toolkit_cli]` table is lossless, stable, and reads back via `tomllib.loads(...)` + `json.loads(...)`. Ugly but parseable. No new dependencies: hand-emit the TOML (escape `"""` in body; standard TOML triple-quoted string rules).

Register in `TRANSLATORS`:

```python
("gemini", "command"): _translate_gemini_command,
```

#### `(gemini, agent)` — verify-time decision

Default: no translator (raw symlink, like `(claude, agent)`). Build phase MUST verify by linking a toolkit-shipped agent (e.g. `code-reviewer`) and checking it round-trips through Gemini's `/agents list`. If Gemini silently drops the agent (as OpenCode/Codex did with skills — see `_translate_opencode_skill` docstring), the build adds a `_translate_gemini_agent` before opening the PR. The translator's required frontmatter shape is determined empirically at that point, mirroring the discovery process documented in existing translator docstrings.

#### `(gemini, skill)` — no translator

Skills are directories; the toolkit's wrapper layout matches Gemini's `SKILL.md`-with-frontmatter convention. Same as `(claude, skill)`.

### 5. Link library (`commands/_link_lib.py`)

- `HARNESS_HOMES` gains `"gemini": ".gemini"`.
- `_CACHE_LAYOUT` gains `"gemini": {"user": (".gemini", CACHE_DIR_NAME), "project": (".gemini", CACHE_DIR_NAME)}`.
- `_translated_slot_filename` gains a branch: `if harness == "gemini" and kind == "command": return f"{slug}.toml"`. Other gemini kinds fall through to bare slug (dir-symlink for skills) or are not translated.
- `_translate_slot_layout`: the existing `endswith(".md")` derivation becomes `endswith((".md", ".toml"))` so TOML cache files get `"file"` slot layout. (Alternative: just hard-branch on `harness == "gemini" and kind == "command"`. Either is fine; pick whichever reviewer comments resolve.)

### 6. Doctor (`doctor/harness_homes.py`)

- The hardcoded "all 4 harness homes" string at line 33 becomes "all 5". Derive from `len(ALL_HARNESSES)` if straightforward, otherwise mechanical edit.

### 7. Docs

- `docs/agent-toolkit/harness-matrix.md`: add a `| Gemini |` column to the header and every row. Cell values per the matrix in this spec.
- `README.md` line 3: append "and Gemini CLI" to the supported-harness list. Update line 55 (MCP support note) — gemini ships with a real MCP adapter, so remove from the "pending" list.

### 8. Tests

- `tests/test_support.py`: update the `ALL_HARNESSES` canary tuple (line 19). Add spot-checks for new `(gemini, *)` cells in `_USER_TARGETS` / `_PROJECT_TARGETS`.
- `tests/test_harness_matrix.py`: extend `_HARNESS_ORDER` and the `_ROW_RE` named-group regex to include a `gemini` group. Test asserts the doc and code agree.
- `tests/test_mcp_adapters_gemini.py` (new): mirror `tests/test_mcp_adapters_opencode.py` and `tests/test_mcp_adapters_claude.py`. Cover: `config_target` for both scopes, `list_installed` round-trip, `entry_drift` for modified entries, empty-file / missing-file behaviour.
- `tests/test_translators.py` (existing): add cases for `_translate_gemini_command` — minimum (description + prompt only), with wrapper round-trip, body containing triple-quotes (escape correctness).
- `tests/test_link_lib.py` (existing): add `_translated_slot_filename` and `_translate_slot_layout` assertions for `(gemini, command)`.

## Acceptance criteria

Mapping the issue's DoD onto this design:

- [x] `gemini` in `ALL_HARNESSES` and `_KNOWN_HARNESSES` — sections 1 & 2
- [x] User-scope and project-scope path entries for all four supported kinds — section 1
- [x] `list`, `link`, `doctor`, translator dispatch recognise `gemini` — sections 1, 4, 5, 6
- [x] `harness_adapters/gemini.py` exists — section 3 (real adapter, not placeholder)
- [x] Test coverage updated — section 8
- [x] README / docs updated — section 7
- [x] Empirical agent-translator check during build — section 4

## Open questions resolved during brainstorming

| Question | Resolution |
|---|---|
| MCP placeholder vs real adapter? | Real `ConfigFileAdapter`. Gemini MCP is live; no reason to defer. |
| Which kinds for gemini? | skill + agent + command + mcp (full parity; all four documented by Gemini). |
| Project-scope home? | `.gemini/` (verified via official docs — workspace settings live there). |
| Markdown commands in Gemini's TOML dir? | In scope. Ship a TOML translator. |
| Wrapper round-trip in TOML? | JSON-encoded strings under `[agent_toolkit_cli]`. Lossless, no new deps. |
| Does gemini need an agent translator? | Empirical verification during build. Default no; add if Gemini drops raw symlinks. |

## Risks and gotchas (carried from scout brief)

- `tests/test_harness_matrix.py:_ROW_RE` is a named-group regex with exactly four groups today. Both the regex and `_HARNESS_ORDER` must be updated in the same edit, or the test silently misreads rows.
- `tests/test_support.py:19` hardcodes the full tuple. Updating `ALL_HARNESSES` alone won't suffice.
- `HARNESS_HOMES` is consulted by `harness_home_path` which raises `KeyError` (not a graceful error) for unknown harnesses. The gemini entry must land before any code path can exercise the harness.
- Gemini's MCP key is `mcpServers` (camelCase), not OpenCode's `mcp`. Do not copy-paste OpenCode's merge logic.
- TOML triple-quoted strings need careful escaping if the markdown body itself contains `"""`. Hand-emitter must handle this.

## Out of scope

Per issue:

- Full overhaul of harness portability rules in conventions.
- Gemini-specific frontmatter quirks beyond the four kinds above (e.g. hooks, plan-mode artifacts, extensions registry).
