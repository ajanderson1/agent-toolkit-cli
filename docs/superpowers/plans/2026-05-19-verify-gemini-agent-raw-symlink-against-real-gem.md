# Fix `(gemini, agent)` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change `(gemini, agent)` from raw symlink to translate cell so Gemini's loader actually surfaces toolkit-linked agents.

**Architecture:** Three coupled edits + matrix update + tests. Add `_translate_gemini_agent` translator (mirrors `_translate_opencode_skill` — top-level `name` + `description` + wrapper block). Extend `_slot_filename` so `(gemini, agent)` returns `<slug>.md` (was bare `<slug>`). Register translator. Update harness-matrix doc. New unit tests.

**Tech Stack:** Python 3.13 · `uv` · `pytest` · `ruff` · `pyyaml` (for round-trip checks).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_toolkit_cli/_translators.py` | translator functions + `TRANSLATORS` registry | **Modify** — add `_translate_gemini_agent`; register tuple |
| `src/agent_toolkit_cli/commands/_link_lib.py` | slot-filename + layout logic | **Modify** — extend `_slot_filename` so `(gemini, agent)` returns `.md` |
| `src/agent_toolkit_cli/harness_adapters/gemini.py` | gemini adapter (docstring) | **Modify** — one-line doc note pointing at #97 |
| `docs/agent-toolkit/harness-matrix.md` | canonical harness ↔ kind table | **Modify** — agent row gemini cell `symlink` → `translate`; refresh prose |
| `tests/test_translators.py` | translator unit tests | **Modify** — 3 new tests for `_translate_gemini_agent` |
| `tests/test_link_lib.py` | slot/layout unit tests | **Modify** — 2 new tests for `(gemini, agent)` |

Existing matrix-parser test (`tests/test_harness_matrix.py`) catches the row mechanism update automatically from the doc edit.

---

### Task 1: Add `_translate_gemini_agent` translator + register

**Files:**
- Modify: `src/agent_toolkit_cli/_translators.py:101` (insert new function after `_translate_opencode_skill`); registry tuple at `:175-181`

- [ ] **Step 1: Write the failing test (translator minimum shape)**

Append to `tests/test_translators.py`:

```python
def _make_gemini_agent_record(slug: str, metadata: dict) -> AssetRecord:
    """Build an AssetRecord for an agent with the given raw metadata dict."""
    from agent_toolkit_cli.walker import Asset, AssetRecord
    asset = Asset(kind="agent", slug=slug, path=Path(f"/fake/agents/{slug}.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_gemini_agent_minimum():
    """Minimum: top-level name + description, body preserved, wrapper present."""
    import yaml

    record = _make_gemini_agent_record(
        "demo-agent",
        {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "demo-agent", "description": "Verify cross-harness."},
        },
    )
    body = "You are DemoBot.\n"
    out = _translate_gemini_agent(record, body).decode("utf-8")
    assert out.startswith("---\n")
    fm_text, _, body_out = out[4:].partition("\n---\n")
    fm = yaml.safe_load(fm_text)
    assert fm["name"] == "demo-agent"
    assert fm["description"] == "Verify cross-harness."
    assert body_out == body
```

Add `_translate_gemini_agent` to the import block at lines 12-17:

```python
from agent_toolkit_cli._translators import (
    _translate_codex_skill,
    _translate_gemini_agent,
    _translate_gemini_command,
    _translate_opencode_agent,
    _translate_opencode_command,
    _translate_opencode_skill,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_translators.py::test_translate_gemini_agent_minimum -v`
Expected: FAIL — ImportError on `_translate_gemini_agent`.

- [ ] **Step 3: Add the translator function in `_translators.py`**

Insert after `_translate_opencode_skill` (around line 101):

```python
def _translate_gemini_agent(record: AssetRecord, body: str) -> bytes:
    """Gemini's loader requires top-level `name` and `description` in the YAML
    frontmatter. The toolkit's v1alpha2 wrapper nests these under metadata.*,
    so the loader either rejects the agent or loads it with an empty
    name/description (#97).

    Output mirrors `_translate_opencode_skill` — top-level `name` and
    `description` plus `agent_toolkit_cli` wrapper block for round-trip
    traceability. Empirically verified against gemini 0.40.1
    (`docs/core/subagents.md` requires `*.md` files with top-level name +
    description; bare-named files or wrapper-only frontmatter are dropped).
    """
    fm = {
        "name": _name(record),
        "description": _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)
```

- [ ] **Step 4: Register in `TRANSLATORS` dict**

In the `TRANSLATORS` dict at the bottom of `_translators.py`, add the line in alphabetical-pair order (currently after `("gemini", "command")`):

```python
TRANSLATORS: dict[tuple[str, str], Callable[[AssetRecord, str], bytes]] = {
    ("opencode", "agent"): _translate_opencode_agent,
    ("opencode", "command"): _translate_opencode_command,
    ("codex", "skill"): _translate_codex_skill,
    ("opencode", "skill"): _translate_opencode_skill,
    ("gemini", "command"): _translate_gemini_command,
    ("gemini", "agent"): _translate_gemini_agent,
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_translators.py::test_translate_gemini_agent_minimum -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/_translators.py tests/test_translators.py
git commit -m "feat(#97): add _translate_gemini_agent (top-level name+description)"
```

---

### Task 2: Wrapper round-trip + body preservation tests

**Files:**
- Modify: `tests/test_translators.py` (append)

- [ ] **Step 1: Add wrapper round-trip test**

```python
def test_translate_gemini_agent_round_trips_wrapper():
    """metadata + spec preserved verbatim under agent_toolkit_cli."""
    import yaml

    md = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {"name": "a", "description": "d", "tags": ["x", "y"]},
        "spec": {"harnesses": ["gemini"], "origin": "first-party"},
    }
    record = _make_gemini_agent_record("a", md)
    out = _translate_gemini_agent(record, "body\n").decode("utf-8")
    fm_text, _, _ = out[4:].partition("\n---\n")
    fm = yaml.safe_load(fm_text)
    assert fm["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"
    assert fm["agent_toolkit_cli"]["metadata"]["tags"] == ["x", "y"]
    assert fm["agent_toolkit_cli"]["spec"]["harnesses"] == ["gemini"]
```

- [ ] **Step 2: Add TRANSLATORS-dict registration test**

```python
def test_translators_dict_includes_gemini_agent():
    """Regression guard: (gemini, agent) must be in TRANSLATORS."""
    from agent_toolkit_cli._translators import TRANSLATORS

    assert ("gemini", "agent") in TRANSLATORS
    assert TRANSLATORS[("gemini", "agent")] is _translate_gemini_agent
```

- [ ] **Step 3: Run both tests**

Run: `uv run pytest tests/test_translators.py -k "gemini_agent" -v`
Expected: 3 PASS (the minimum from Task 1 + these two).

- [ ] **Step 4: Commit**

```bash
git add tests/test_translators.py
git commit -m "test(#97): add wrapper round-trip and TRANSLATORS registration tests"
```

---

### Task 3: Fix `_slot_filename` for `(gemini, agent)`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py:101-116`
- Modify: `tests/test_link_lib.py` (append two tests near the gemini-command tests at line 455)

- [ ] **Step 1: Write the failing slot-filename test**

Append to `tests/test_link_lib.py`:

```python
def test_slot_filename_gemini_agent_uses_md_extension():
    from agent_toolkit_cli.commands._link_lib import _slot_filename

    assert _slot_filename("demo", "agent", "gemini") == "demo.md"


def test_translate_slot_layout_gemini_agent_is_file():
    from agent_toolkit_cli.commands._link_lib import _translate_slot_layout

    assert _translate_slot_layout("gemini", "agent") == "file"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_link_lib.py -k "gemini_agent" -v`
Expected: FAIL — `_slot_filename` returns `"demo"`, not `"demo.md"`.

- [ ] **Step 3: Extend `_slot_filename`**

In `src/agent_toolkit_cli/commands/_link_lib.py:101-116`, replace:

```python
def _slot_filename(slug: str, kind: str, harness: str) -> str:
    """Return the filename used for the slot symlink in this (harness, kind).

    File-slot kinds get an extension matching the harness:
      - `(opencode|claude, agent|command)` → `<slug>.md`
      - `(gemini, agent)` → `<slug>.md` — Gemini's loader globs `*.md` for
        agents and requires top-level name/description (#97); the toolkit's
        `_translate_gemini_agent` lifts those out of the v1alpha2 wrapper.
      - `(gemini, command)` → `<slug>.toml`
    Directory-slot kinds — and any unsupported pair — get the bare `<slug>`.

    Callers can detect the slot shape from the result: any extension ⇒
    file-slot; otherwise directory-slot or non-translated.
    """
    if harness == "gemini" and kind == "command":
        return f"{slug}.toml"
    if (kind in {"agent", "command"} and harness in {"opencode", "claude"}) \
       or (harness == "gemini" and kind == "agent"):
        return f"{slug}.md"
    return slug
```

`_translate_slot_layout` does not need changes — its `.endswith(".md")` branch picks up the new case automatically.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_link_lib.py -k "gemini" -v`
Expected: all gemini slot tests PASS (the existing `command` ones + the two new `agent` ones).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py tests/test_link_lib.py
git commit -m "fix(#97): (gemini, agent) slot filename now <slug>.md (was bare slug)"
```

---

### Task 4: Update harness-matrix doc + gemini.py docstring

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md:67` (agent row, gemini column)
- Modify: prose section below the table that discusses agent dispatch (search for "agent" subsection)
- Modify: `src/agent_toolkit_cli/harness_adapters/gemini.py` (module docstring)

- [ ] **Step 1: Update the matrix cell**

In `docs/agent-toolkit/harness-matrix.md` agent row (line ~67), change the gemini column from:

```
symlink → `~/.gemini/agents/<slug>.md`
```

to:

```
translate → `~/.gemini/agents/<slug>.md` (cache: `~/.gemini/.agent-toolkit-cache/agent/<slug>.md`) — emits gemini-shaped frontmatter with top-level `name` and `description` plus `agent_toolkit_cli` wrapper block (mirrors OpenCode skill shape). #97
```

- [ ] **Step 2: Update agent-prose section if one exists**

Search for any agent-row prose explanation below the table. If it mentions Gemini agents using symlinks, update to translate. Use:

```bash
grep -n -B2 -A8 "gemini.*agent\|agent.*gemini" docs/agent-toolkit/harness-matrix.md
```

Apply edits where the previous claim said "symlink".

- [ ] **Step 3: Update gemini.py module docstring**

Find the module-level docstring at the top of `src/agent_toolkit_cli/harness_adapters/gemini.py`. Add a one-line bullet point or note in the same section that lists agent/skill/command behavior:

```
- (gemini, agent): translate (per #97) — top-level name+description required.
```

If there is no existing list, add a single-line note referencing #97.

- [ ] **Step 4: Run the matrix-parser test**

Run: `uv run pytest tests/test_harness_matrix.py -v`
Expected: PASS (matrix-parser should pick up the row change cleanly).

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (685+ existing + 5 new).

- [ ] **Step 6: Commit**

```bash
git add docs/agent-toolkit/harness-matrix.md src/agent_toolkit_cli/harness_adapters/gemini.py
git commit -m "docs(#97): matrix + gemini.py docstring — agent cell is translate"
```

---

### Task 5: Full pre-flight CI

**Files:** none (verification only)

- [ ] **Step 1: Run pytest**

```bash
uv run pytest -q | tee assets/verification/97/preflight-pytest.log
```

Expected: all tests pass.

- [ ] **Step 2: Run ruff**

```bash
uv run ruff check src tests | tee assets/verification/97/preflight-ruff.log
```

Expected: no findings.

If either fails: STOP. Surface the log to the user. Do not proceed.

---

### Task 6: Empirical verification (re-run the link recipe)

**Files:**
- Read: `~/GitHub/agent-toolkit/agents/demo-agent.md` (temp-edit, will revert)
- Write: `assets/verification/97/link-output.txt`, `slot-file.txt`, `cache-head.txt`

- [ ] **Step 1: Temp-add gemini to demo-agent harnesses**

```bash
# Manual edit — add `- gemini` to spec.harnesses list in
# ~/GitHub/agent-toolkit/agents/demo-agent.md
```

- [ ] **Step 2: Run link**

```bash
uv run agent-toolkit-cli link user gemini agent:demo-agent | tee assets/verification/97/link-output.txt
```

- [ ] **Step 3: Verify slot file shape**

```bash
ls -la ~/.gemini/agents/ | tee assets/verification/97/slot-file.txt
```

Expected: `demo-agent.md` (with `.md` extension), symlinked to `~/.gemini/.agent-toolkit-cache/agent/demo-agent.md`.

```bash
head -15 ~/.gemini/agents/demo-agent.md | tee assets/verification/97/cache-head.txt
```

Expected: YAML frontmatter with top-level `name: demo-agent` and `description: …` (matching the asset's metadata.description), followed by `agent_toolkit_cli:` wrapper block.

- [ ] **Step 4: Restore demo-agent.md**

Revert the temp edit. Confirm `git diff` on `~/GitHub/agent-toolkit` shows no change to `agents/demo-agent.md`.

- [ ] **Step 5: Clean up**

```bash
uv run agent-toolkit-cli unlink user gemini agent:demo-agent 2>&1 | tee -a assets/verification/97/link-output.txt
```

Or, if unlink isn't trivial without the harnesses entry still present, just `rm ~/.gemini/agents/demo-agent.md` and `rm -rf ~/.gemini/.agent-toolkit-cache/agent/`.

- [ ] **Step 6: Verdict line to flow.log**

```bash
echo "[$(date +%H:%M:%S)] empirical verify: slot file has .md, top-level name/description confirmed" >> assets/verification/97/flow.log
```

---

## Self-Review

Run the in-PR self-review pass per `superpowers:requesting-code-review`:

- Diff: `git diff origin/main...HEAD`
- Capture verdict + findings to `assets/verification/97/review-1.md`
- Apply fixes per `superpowers:receiving-code-review` (verify each finding; log disagreements to flow.log)
- Max 1 retry. If review-2 still does not PASS in `--auto` mode → safety stop.

---

## Acceptance Checklist

- [ ] `_translate_gemini_agent` defined and registered
- [ ] `_slot_filename("x", "agent", "gemini") == "x.md"`
- [ ] `_translate_slot_layout("gemini", "agent") == "file"`
- [ ] Matrix doc shows `translate` in agent row, gemini column
- [ ] gemini.py docstring references #97
- [ ] 5 new tests pass; full suite green
- [ ] Empirical link produces `~/.gemini/agents/demo-agent.md` with top-level `name` + `description`
- [ ] Self-review PASS (or needs-changes-applied-resolved)
