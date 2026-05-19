# Implementation plan: (codex, agent) adapter

**Spec:** [`../specs/2026-05-19-codex-agent-adapter-design.md`](../specs/2026-05-19-codex-agent-adapter-design.md)
**Issue:** #140

## Pre-resolved design decisions

1. **Strategy:** symlink + per-asset translator. Same code path as `(codex, skill)` and `(gemini, command)`. No new strategy class.
2. **Slot layout:** `file` — `~/.codex/agents/<slug>.toml` is a symlink to a per-scope cache file.
3. **Cache file extension:** currently `_render_to_cache` hardcodes `<slug>.md`. The slot symlink filename and the cache file name don't actually have to match (only the symlink name matters for harness discovery), but the mismatch is ugly. Fix: derive the cache extension from `_slot_filename(slug, kind, harness)`. This is a one-line refactor that also cleans up `(gemini, command)` incidentally.
4. **TOML rendering helpers:** reuse `_toml_basic_string` and `_toml_multiline_string` from `_translators.py` (already used by `_translate_gemini_command`).
5. **Toolkit-provenance table:** emit `[agent_toolkit_cli]` with `apiVersion` + JSON-encoded `metadata` + `spec`, exactly like `_translate_gemini_command`.
6. **No optional codex agent fields** in this PR (model, sandbox_mode, etc.). Stay at the three required fields.

## Tasks

### Task 1 — Support matrix rows

**File:** `src/agent_toolkit_cli/_support.py`

- Add `("codex", "agent"): "{home}/.codex/agents"` to `_USER_TARGETS` (alphabetical placement — between `(codex, hook)` and `(opencode, skill)`).
- Add `("codex", "agent"): ".codex/agents"` to `_PROJECT_TARGETS` (between `(codex, skill)` and `(opencode, skill)`).
- Update the module docstring's "remaining matrix gaps" comment — drop the implicit reference to #140 as a gap, leave the others.

**Tests:** `tests/test_support.py` — the existing matrix-shape test enumerates supported pairs; add `(codex, agent)` to the expected set. Also `tests/test_harness_matrix.py` if it asserts on per-harness kind counts.

### Task 2 — Translator

**File:** `src/agent_toolkit_cli/_translators.py`

Add function `_translate_codex_agent(record, body) -> bytes`:

```toml
name = "<slug>"
description = "<metadata.description>"
developer_instructions = """
<body>
"""

[agent_toolkit_cli]
apiVersion = "<record.apiVersion>"
metadata = "<json-encoded metadata block>"
spec = "<json-encoded spec block>"   # only if present
```

- Use `_toml_basic_string` for `name`, `description`, and the wrapper scalars.
- Use `_toml_multiline_string` for `developer_instructions`.
- Mirror `_translate_gemini_command`'s emission pattern exactly — same helpers, same conditional `spec` block.
- The `name` field uses the asset slug (Codex's filename convention), NOT `metadata.name` — keeps slot filename ↔ TOML name in sync. (`metadata.name` may diverge from the slug for human-display reasons; the filename / TOML `name` must match for codex's loader.)

Wait — re-check: the codex docs say "name field is source of truth, filename matches name by convention." Use the slug (= filename minus extension) for both. The slug comes from `record.path.stem` or similar; verify the exact accessor when implementing. If `metadata.name` is the canonical source in this codebase, use that. Pick one and be consistent. **Default: use the slug to match the slot filename.**

Register in `TRANSLATORS`:
```python
("codex", "agent"): _translate_codex_agent,
```

**Tests:** new `tests/test_translators.py::test_translate_codex_agent_*` covering:
- required-field rendering;
- body becomes `developer_instructions` as multiline string;
- markdown body with triple-backtick fences round-trips through `_toml_multiline_string` correctly (escape behaviour for `"""` inside body);
- `[agent_toolkit_cli]` table present with JSON-encoded `metadata` + (when present) `spec`;
- `tomllib.loads(rendered)` succeeds — proves valid TOML.

### Task 3 — Slot filename + layout

**File:** `src/agent_toolkit_cli/commands/_link_lib.py`

1. **`_slot_filename`** (line ~101): add a clause for `(codex, agent)`. Cleanest form — extend the gemini-command short-circuit:

   ```python
   if (harness == "gemini" and kind == "command") or (harness == "codex" and kind == "agent"):
       return f"{slug}.toml"
   ```

2. **`_translate_slot_layout`** (line ~134): add the symmetric short-circuit for `(codex, agent)` so the function returns `"file"`. Currently the function returns `"file"` only when `_slot_filename().endswith(".md")` OR via the explicit gemini-command override. Add a parallel override for codex-agent (or, cleaner: change the underlying condition to `endswith((".md", ".toml"))` — but the gemini-command override remains because gemini-command's `.toml` filename was already special-cased explicitly. Picking the explicit-override route keeps the diff localised and matches existing precedent).

3. **`_render_to_cache`** (line ~183): derive cache extension from `_slot_filename`:

   ```python
   if layout == "file":
       cache_dir = cache_root
       cache_path = cache_dir / _slot_filename(slug, kind, harness)
       slot_target = cache_path
   ```

   This is a refactor that also fixes `(gemini, command)`'s incidentally-ugly `.md` cache filename. Run existing tests to verify nothing relied on the old `<slug>.md` cache name (greppable: there's only one consumer — `_render_to_cache` itself — but old test fixtures may have asserted on cache paths). If a test fails, update its expectation to match the new (correct) extension.

**Tests:**
- Extend `tests/test_link_lib.py`:
  - `test_slot_filename_codex_agent_uses_toml_extension`
  - `test_translate_slot_layout_codex_agent_is_file`
- If existing tests asserted on `<slug>.md` cache path for gemini-command, update to `.toml`.

### Task 4 — Link / unlink integration

**Files:** no new code expected — the existing `maybe_link` path handles file-layout translated cells. Verify by running tests.

**New tests:** `tests/test_link_codex_agent.py` (mirror `tests/test_link_codex_skill.py`'s structure if present; otherwise mirror `tests/test_cli_link.py`'s gemini-command scenarios):
1. `test_link_user_scope_creates_toml_file` — link an agent, assert `~/.codex/agents/<slug>.toml` symlinks to a cache file, cache file is valid TOML with the three required fields.
2. `test_link_project_scope_creates_toml_file` — same for `<project>/.codex/agents/<slug>.toml`.
3. `test_drift_rewrites_cache` — hand-edit the cache TOML; re-link; cache restored.
4. `test_unlink_removes_slot_and_cache` — unlink, slot symlink gone, cache pruned.
5. `test_unlink_after_allowlist_clear` — projection cleanup for stale entries (matches the `(codex, hook)` parity test).

Use `tmp_path` + `monkeypatch.setenv("HOME", ...)` per existing conventions in the test suite.

### Task 5 — Doctor & list integration

**Files:**
- `src/agent_toolkit_cli/doctor/symlinks.py` — translator-aware drift check already covers the new pair via `TRANSLATORS` membership.
- `src/agent_toolkit_cli/commands/_list_json.py` — same.

**Verify:** no code change expected. Tests:
- `tests/test_doctor_*.py` — any scope-coverage test should include `(codex, agent)` in expected rows. Update fixture data.
- `tests/test_list_json.py` — coverage table includes the new cell.

If grep reveals an explicit allowlist of supported pairs in any doctor module, extend it. (None expected — they read from `_support.SUPPORTED_PAIRS`.)

### Task 6 — Inventory / TUI smoke

**Files:** `src/agent_toolkit_cli/inventory.py`, TUI widget if applicable.

**Verify:** the asset-grid table reads supported pairs from `_support`; should render the new cell automatically. Run `agent-toolkit-cli inventory` against a fixture to confirm.

**No expected test change** beyond updating any snapshot fixture that enumerates pairs.

### Task 7 — Fixture asset

**File:** `tests/_fixtures/<something>/codex-agent-test.md` — add (or reuse an existing) `kind: agent` fixture that declares `spec.harnesses: [codex]`. Used by the link-integration tests.

If a generic agent fixture already exists with `spec.harnesses` open to codex, **no new fixture needed** — just link it through codex in the new tests.

### Task 8 — Docs

**Files:**
- `README.md` (support matrix table).
- `docs/agent-toolkit/cli.md` (matrix if duplicated there).

Add the new row. Keep the wording terse — match the existing rows' style.

### Task 9 — Verify

1. Run full test suite: `uv run pytest`. Expect all green.
2. Run lint: `uv run ruff check` / format check per `verify.sh` if present.
3. Manually render a fixture: instantiate the translator on a sample asset; `tomllib.loads` the result; confirm `name`, `description`, `developer_instructions` shape.
4. Attach: the rendered sample TOML to `assets/verification/140/sample-rendered.toml`. Add a one-line trace of `link` output to `assets/verification/140/link-trace.txt`.

## Execution order

Tasks 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. Each task self-contained; no parallel execution needed.

## Risks / unknowns

- **`record.slug` accessor name:** the spec mentions `record.path.stem` or similar — verify the exact attribute when implementing Task 2. If `AssetRecord` exposes the slug differently, adjust.
- **JSON encoding of `spec`:** if the asset's spec block contains keys with chars that break TOML basic strings (newlines, embedded triple quotes), the existing helpers handle the escape. Verified by `_translate_gemini_command` already in production.
- **`gemini-command` cache rename collateral:** Task 3.3's refactor changes the cache file extension for gemini-command from `.md` to `.toml`. Old caches on disk become orphaned. The linker's drift check will detect and rewrite on next link. Surface this in the PR body so reviewers know to expect stale `.md` files under `.gemini/agent-toolkit-cache/command/` if they had previously linked.
