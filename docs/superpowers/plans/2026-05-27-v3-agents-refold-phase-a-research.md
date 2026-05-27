# v3.0.0 Agents Refold — Phase A (Research) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a citation-grade `agent` (subagent) compatibility table covering all 54 supported harnesses in `docs/agent-toolkit/harness-matrix.md`, guarded by a parity test, and file the v3.0.0 epic GitHub issue with that table as its work surface — so Phase B (implementation) can be planned against hard data.

**Architecture:** This is research-orchestration, not application code. The orchestrator dispatches ~9 research subagents (one per harness family), each returning a **markdown table fragment** of `agent`-row cells for its batch. The orchestrator assembles the fragments into a freshly-created `docs/agent-toolkit/harness-matrix.md` (the v1 doc was deleted in the strip-back; we recreate it Phase-A-scoped to the `## Subagent (agent kind) support — all harnesses` section, a 54-row per-harness table). A new parity test asserts every one of the 54 catalog harnesses appears exactly once in that table with a recognised verdict keyword. Finally a GitHub issue is filed linking the table.

**Tech Stack:** Python 3.12+, pytest (parity test), `gh` CLI (issue), the existing harness catalog `src/agent_toolkit_cli/skill_agents.py` (54 harnesses + `universal`), and the Task tool (research subagents). No runtime/CLI/TUI code changes in Phase A.

---

## Why Phase A is self-contained

Phase A ships three concrete, testable artifacts and nothing else:

1. A new **subagent-support table** in `harness-matrix.md` (all 54 harnesses).
2. A **parity test** (`tests/test_subagent_matrix.py`) that fails if the table drops a harness or uses an unrecognised verdict — making the table machine-checked, per the conventions "automate consistency" principle.
3. A **GitHub issue** for the v3.0.0 epic.

Phase B (adapters, install/lock kind-generalization, TUI `KindsSidebar`, CLI `agent` verbs incl. `agent import`) is explicitly **out of scope here** and gets its own `writing-plans` plan once this table lands, because its key decisions (CLI shape, generalize-in-place vs parallel modules, lock-schema break) depend on *which* harnesses come back `supported`.

## File structure

| File | Responsibility | Phase A action |
|---|---|---|
| `docs/agent-toolkit/harness-matrix.md` | SSOT for `(kind × harness)` support. | **Create** — the doc was deleted in the strip-back (commit `04aed66`, #164) and exists only at tag `v1.0.0`. Recreate it with a header + reused "Mechanisms" vocabulary + the new `## Subagent (agent kind) support — all harnesses` section (54-row table). The legacy 5-column grid is NOT reintroduced in Phase A. |
| `tests/test_subagent_matrix.py` | Parity test for the new 54-row table. | **Create** — asserts all 54 catalog harnesses present, verdicts recognised, supported rows carry mechanism+path+citation. |
| `docs/agent-toolkit/research/subagent-fragments/*.md` | Scratch storage for each research agent's returned fragment + "what I checked" trail. | **Create** (9 files) — input to assembly; kept in-repo as the audit trail behind each cell. |
| GitHub issue (no file) | v3.0.0 epic tracking. | **Create** via `gh issue create`. |

The verdict/mechanism vocabulary is **reused verbatim** from the v1 matrix's "Mechanisms" section (`symlink`, `translate`, `config_file`, `config_file+folder`, `dual-symlink`, `unsupported (gap)`, `unsupported (by design)`) plus one new verdict `unknown` for time-boxed-no-evidence harnesses. Do not invent new mechanism words. The v1 Mechanisms prose is recoverable via `git show v1.0.0:docs/agent-toolkit/harness-matrix.md`.

---

## Task 1: Establish the canonical 54-harness list as test data

**Files:**
- Test: `tests/test_subagent_matrix.py`

This task pins down the exact set of harness names the table must cover, sourced from the live catalog, before any research runs. It produces a failing test (table doesn't exist yet) that defines "done" for assembly.

- [ ] **Step 1: Confirm the live harness names**

Run:
```bash
python -c "from agent_toolkit_cli.skill_agents import AGENTS; \
print(sorted(set(AGENTS) - {'universal'}))"
```
Expected: a sorted list of 54 names. `AGENTS` is a module-level `dict[str, AgentConfig]` keyed by harness name (defined at `src/agent_toolkit_cli/skill_agents.py:48`); the synthetic `universal` entry is excluded. The 54 names (verified against the live catalog) are:

```
adal aider-desk amp antigravity augment bob claude-code cline codearts-agent
codebuddy codemaker codestudio codex command-code continue cortex crush cursor
deepagents devin dexto droid firebender forgecode gemini-cli github-copilot
goose hermes-agent iflow-cli junie kilo kimi-cli kiro-cli kode mcpjam
mistral-vibe mux neovate openclaw opencode openhands pi pochi qoder qwen-code
replit roo rovodev tabnine-cli trae trae-cn warp windsurf zencoder
```

- [ ] **Step 2: Write the failing parity test**

Create `tests/test_subagent_matrix.py`:

```python
"""Parity test for the all-harness subagent (agent kind) support table.

The table lives in docs/agent-toolkit/harness-matrix.md under the heading
"## Subagent (agent kind) support — all harnesses". Every harness in the
catalog (agent_toolkit_cli.skill_agents, excluding the synthetic `universal`
entry) must appear exactly once with a recognised verdict. Supported rows
must additionally carry a mechanism keyword, a target path, and a citation.

This is the Phase A gate: the table is the contract Phase B implements against.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent_toolkit_cli import skill_agents

_REPO_ROOT = Path(__file__).parent.parent
_DOC_PATH = _REPO_ROOT / "docs" / "agent-toolkit" / "harness-matrix.md"

# Verdict keywords a cell may start with. "unknown" is new in v3.0.0 Phase A
# for time-boxed-no-evidence harnesses; the rest reuse the matrix vocabulary.
_VERDICTS = (
    "symlink",
    "translate",
    "config_file+folder",
    "config_file",
    "dual-symlink",
    "unsupported (gap)",
    "unsupported (by design)",
    "unknown",
)

# Section heading that contains the 54-row table.
_SECTION_HEADING = "## Subagent (agent kind) support — all harnesses"

# Row shape: | `<harness>` | <verdict cell> | <mechanism> | <path> | <format> | <citation> |
_ROW_RE = re.compile(
    r"^\|\s*`(?P<harness>[a-z][a-z0-9-]*)`\s*\|"
    r"(?P<verdict>[^|]+)\|"
    r"(?P<mechanism>[^|]*)\|"
    r"(?P<path>[^|]*)\|"
    r"(?P<fmt>[^|]*)\|"
    r"(?P<citation>[^|]*)\|"
)


def _catalog_harnesses() -> set[str]:
    """All catalog harness names except the synthetic `universal` entry.

    `skill_agents.AGENTS` is a dict[str, AgentConfig] keyed by harness name.
    """
    return set(skill_agents.AGENTS) - {"universal"}


def _parse_section() -> dict[str, dict[str, str]]:
    """Return {harness: {verdict, mechanism, path, fmt, citation}} from the table."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    if _SECTION_HEADING not in text:
        return {}
    section = text.split(_SECTION_HEADING, 1)[1]
    # Stop at the next H2 so we only parse this section's rows.
    section = re.split(r"^## ", section, maxsplit=1, flags=re.MULTILINE)[0]
    rows: dict[str, dict[str, str]] = {}
    for line in section.splitlines():
        m = _ROW_RE.match(line.strip())
        if m is None:
            continue
        rows[m.group("harness")] = {
            "verdict": m.group("verdict").strip(),
            "mechanism": m.group("mechanism").strip(),
            "path": m.group("path").strip(),
            "fmt": m.group("fmt").strip(),
            "citation": m.group("citation").strip(),
        }
    return rows


@pytest.fixture(scope="module")
def rows() -> dict[str, dict[str, str]]:
    assert _DOC_PATH.exists(), f"{_DOC_PATH} not found"
    parsed = _parse_section()
    assert parsed, (
        f"No rows parsed under '{_SECTION_HEADING}'. Assemble the table "
        "(Task 4) before this test can pass."
    )
    return parsed


def test_all_catalog_harnesses_present(rows):
    """Every catalog harness must appear exactly once in the table."""
    catalog = _catalog_harnesses()
    table = set(rows)
    missing = catalog - table
    extra = table - catalog
    assert not missing, f"Harnesses missing from subagent table: {sorted(missing)}"
    assert not extra, f"Unknown harnesses in subagent table: {sorted(extra)}"


def test_every_verdict_recognised(rows):
    """Each row's verdict cell must start with a known verdict keyword."""
    bad = {
        h: r["verdict"]
        for h, r in rows.items()
        if not r["verdict"].lower().startswith(_VERDICTS)
    }
    assert not bad, f"Rows with unrecognised verdict: {bad}"


def test_supported_rows_have_mechanism_path_citation(rows):
    """A 'supported' verdict (symlink/translate/config_file/dual-symlink) must
    carry a non-empty mechanism, path, and citation."""
    supported_prefixes = ("symlink", "translate", "config_file", "dual-symlink")
    incomplete = {
        h: r
        for h, r in rows.items()
        if r["verdict"].lower().startswith(supported_prefixes)
        and not (r["mechanism"] and r["path"] and r["citation"])
    }
    assert not incomplete, (
        f"Supported rows missing mechanism/path/citation: {sorted(incomplete)}"
    )
```

- [ ] **Step 3: Run the test to verify it fails for the right reason**

Run: `uv run pytest tests/test_subagent_matrix.py -v`
Expected: FAIL. `test_all_catalog_harnesses_present` (and the others) fail at the `rows` fixture with "No rows parsed under '## Subagent (agent kind) support — all harnesses'" because the section doesn't exist yet. The `_catalog_harnesses()` accessor (`skill_agents.AGENTS`) was verified in Step 1, so the failure should be the missing-section assertion, not an `AttributeError`. If you do see `AttributeError: AGENTS`, the catalog was renamed since this plan — find the real module-level catalog in `skill_agents.py` and update the accessor, then re-run.

- [ ] **Step 4: Commit**

```bash
git add tests/test_subagent_matrix.py
git commit -m "test(matrix): failing parity gate for all-harness subagent table"
```

---

## Task 2: Define the research-agent dispatch brief (shared instructions)

**Files:**
- Create: `docs/agent-toolkit/research/subagent-fragments/_BRIEF.md`

Every research subagent gets the **same** brief so their fragments are uniform and assembly is mechanical. This task writes that brief once. It is reference material — no test.

- [ ] **Step 1: Write the shared brief**

Create `docs/agent-toolkit/research/subagent-fragments/_BRIEF.md`:

````markdown
# Research brief — subagent support per harness (v3.0.0 Phase A)

You are researching whether a specific set of AI coding **harnesses** support
**subagents**, and if so exactly how they locate and load a subagent definition.

## Terminology (do not confuse these)

- **harness** = an AI coding tool (Claude Code, Cursor, Codex, Gemini CLI, Pi…).
  That is what you are researching.
- **subagent / agent kind** = a *spawnable, separately-defined assistant* with
  its own instructions/tools, dropped in as a file (e.g. Claude Code's
  `~/.claude/agents/<slug>.md`). This is the concept you are checking for.
- A subagent is NOT a skill, NOT a slash command, NOT an MCP server, NOT a
  "mode". If a harness only has skills/commands/MCPs and no separately-spawnable
  sub-assistant, its verdict is `unsupported (by design)`.

## Two-stage protocol, per harness

1. **Winnow (time-boxed, ~5 min/harness):** Does this harness have any subagent
   concept distinct from skills/commands/MCPs? Answer yes / no / unknown.
   - `no` with clear evidence → verdict `unsupported (by design)`, one-line reason, done.
   - `unknown` after a bounded search (no public docs, no source, dead project)
     → verdict `unknown — no public evidence found`, list what you checked, done.
   - `yes` → deep-dive.
2. **Deep-dive (only yes/unknown-leaning-yes):** capture the cell fields below
   from CURRENT upstream (re-verify; do not trust 3-week-old data).

## Cell fields to capture (per harness)

- **verdict:** one of `symlink` / `translate` / `config_file` / `config_file+folder`
  / `dual-symlink` (these imply "supported"), or `unsupported (gap)` /
  `unsupported (by design)` / `unknown — no public evidence found`.
  - Use `unsupported (gap)` when the harness *does* support subagents but the
    projection is non-trivial / not yet designed — note why.
- **mechanism:** same keyword as verdict when supported; blank otherwise.
- **user-scope target path** AND **project-scope target path** (e.g.
  `~/.claude/agents/<slug>.md` / `.claude/agents/<slug>.md`).
- **file format:** `markdown+frontmatter` / `TOML` / `JSON`, plus **required**
  and **forbidden** frontmatter fields (e.g. "zod .strict() rejects extra
  top-level keys" → only `name`+`description` allowed).
- **citation:** a CURRENT upstream `file:line` (loader/glob code) or an official
  doc URL. Re-verified this session. No citation copied from memory.

## Output contract (STRICT)

Return ONLY a markdown table fragment — one row per harness you were assigned —
in EXACTLY this column order, followed by a "## What I checked" trail. Do NOT
write to any doc; the orchestrator assembles fragments.

```
| `<harness>` | <verdict> | <mechanism> | <user path> / <project path> | <format + required/forbidden fields> | <citation> |
```

Then:

```
## What I checked — <batch name>
- `<harness>`: <1-3 lines: what sources you hit, what you found / why unknown>
```

Hold the skill-vs-subagent line firmly. When in doubt whether a "mode" or
"profile" is a real subagent, describe it precisely in the trail and lean
`unsupported (gap)` with a note rather than over-claiming `supported`.
````

- [ ] **Step 2: Commit**

```bash
git add docs/agent-toolkit/research/subagent-fragments/_BRIEF.md
git commit -m "docs(research): shared subagent-research brief for Phase A agents"
```

---

## Task 3: Dispatch the research subagents (9 batches)

**Files:**
- Create (one per batch, written by the orchestrator from each agent's returned text): `docs/agent-toolkit/research/subagent-fragments/batch-<N>-<name>.md`

This is the orchestration step. Finalize batch membership against the **live** list from Task 1 Step 1 (every catalog name must land in exactly one batch; cross-check that the union of batches equals the 54 names — no harness dropped, none duplicated). The batches below are the starting partition.

- [ ] **Step 1: Verify the partition covers all 54 exactly once**

Run:
```bash
python - <<'PY'
batches = {
 1: "claude-code openclaw kode mux command-code codemaker".split(),
 2: "gemini-cli antigravity qwen-code iflow-cli".split(),
 3: "opencode crush goose aider-desk".split(),
 4: "codex kimi-cli dexto neovate".split(),
 5: "pi amp cline warp deepagents firebender".split(),
 6: "junie qoder trae trae-cn windsurf cursor continue kilo roo".split(),
 7: "bob codearts-agent cortex devin droid rovodev tabnine-cli zencoder".split(),
 8: "codebuddy codestudio forgecode hermes-agent kiro-cli augment".split(),
 9: "mcpjam mistral-vibe openhands replit github-copilot pochi adal".split(),
}
from agent_toolkit_cli import skill_agents
catalog = set(skill_agents.AGENTS) - {"universal"}
assigned = [h for hs in batches.values() for h in hs]
from collections import Counter
dupes = [h for h, c in Counter(assigned).items() if c > 1]
print("count assigned:", len(assigned), "expected:", len(catalog))
print("missing (in catalog, not assigned):", sorted(catalog - set(assigned)))
print("extra (assigned, not in catalog):", sorted(set(assigned) - catalog))
print("duplicates:", dupes)
PY
```
Expected: `count assigned: 54 expected: 54`, and all three lists empty. **If any harness is missing, extra, or duplicated, fix the `batches` dict before dispatching** — move the missing harness into the most lineage-appropriate batch, drop any name not in the catalog. (Catalog accessor is `skill_agents.AGENTS`, confirmed in Task 1 Step 1.)

- [ ] **Step 2: Dispatch all 9 research agents in parallel**

Dispatch nine `Task` calls (subagent_type `general-purpose`, or `compound-engineering:ce-web-researcher` if available) **in a single message** so they run concurrently. Each prompt is the contents of `_BRIEF.md` followed by that batch's assignment. Template per agent (substitute `<N>`, `<batch name>`, `<space-separated harnesses>`):

```
You are research agent for Batch <N> (<batch name>) of the v3.0.0 subagent
compatibility survey.

<paste full contents of docs/agent-toolkit/research/subagent-fragments/_BRIEF.md>

Your assigned harnesses: <space-separated harnesses>

For each assigned harness, follow the two-stage protocol and return the table
fragment + "What I checked" trail per the Output contract. Return nothing else.
```

Batch names/members (after Step 1 validation):
- Batch 1 — Claude-lineage: claude-code openclaw kode mux command-code codemaker
- Batch 2 — Google/Gemini: gemini-cli antigravity qwen-code iflow-cli
- Batch 3 — OpenCode + forks: opencode crush goose aider-desk
- Batch 4 — Codex/OpenAI-likes: codex kimi-cli dexto neovate
- Batch 5 — Pi + agents-std: pi amp cline warp deepagents firebender
- Batch 6 — JetBrains/IDE: junie qoder trae trae-cn windsurf cursor continue kilo roo
- Batch 7 — Enterprise/cloud: bob codearts-agent cortex devin droid rovodev tabnine-cli zencoder
- Batch 8 — China-market CLIs: codebuddy codestudio forgecode hermes-agent kiro-cli augment
- Batch 9 — Long-tail: mcpjam mistral-vibe openhands replit github-copilot pochi adal

- [ ] **Step 3: Persist each returned fragment verbatim**

As each agent returns, write its full output (table fragment + trail) to
`docs/agent-toolkit/research/subagent-fragments/batch-<N>-<name>.md`. This is the
audit trail and the input to assembly. Do not edit the agent's verdicts here —
just persist.

- [ ] **Step 4: Re-verify v1's 5 baselines against the fresh fragments**

The v1 matrix (tag `v1.0.0`) recorded these 5 — the new fragments MUST either
confirm or explicitly supersede them (harnesses move fast; this is a prior, not truth):
- **claude-code:** `symlink → ~/.claude/agents/<slug>.md`
- **codex:** `translate → ~/.codex/agents/<slug>.toml`, TOML `name`/`description`/`developer_instructions` + `[agent_toolkit_cli]` table (#140)
- **opencode:** `translate → ~/.config/opencode/agents/<slug>.md`, inject `mode: subagent` (project scope `.opencode/`)
- **gemini-cli:** `translate → ~/.gemini/agents/<slug>.md`, **only** `name`+`description` (zod `.strict()`) (#97)
- **pi:** `dual-symlink → ~/.pi/agent/agents/<slug>.md` AND `~/.agents/<slug>.md` via `pi-subagents`; project scope `.pi/agents/` + `.agents/` (#75)

For any of these 5 where the fresh fragment **disagrees** with the v1 baseline,
note the delta in that batch's fragment file under a `## Baseline deltas` heading
(old value → new value → citation). This is the single highest-value sanity check.

- [ ] **Step 5: Commit the raw fragments**

```bash
git add docs/agent-toolkit/research/subagent-fragments/batch-*.md
git commit -m "docs(research): raw subagent-support fragments from 9 batches"
```

---

## Task 4: Assemble the 54-row table into the matrix doc

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md` (append one new H2 section)
- Test: `tests/test_subagent_matrix.py` (from Task 1)

The orchestrator merges all 9 fragments into one table. No agent writes this — single writer avoids races.

- [ ] **Step 1: Create the matrix doc with header + Mechanisms + the new section**

The doc was deleted in the strip-back (commit `04aed66`, #164); recreate it
fresh. First recover the v1 "Mechanisms" prose to reuse the verdict vocabulary
verbatim:

```bash
git show v1.0.0:docs/agent-toolkit/harness-matrix.md | sed -n '/^## Mechanisms/,/^## Matrix/p' > /tmp/v1-mechanisms.md
```

Create `docs/agent-toolkit/harness-matrix.md` with: (1) an H1 + intro paragraph,
(2) the `## Mechanisms` section pasted from `/tmp/v1-mechanisms.md` but trimmed to
the verdicts the subagent table actually uses (`symlink`, `translate`,
`config_file`, `config_file+folder`, `dual-symlink`, `unsupported (gap)`,
`unsupported (by design)`) plus a one-line `unknown` definition, and (3) the
subagent section below. Do NOT reintroduce the legacy 5-column `kind × harness`
grid — that is a Phase B concern when adapters land. Document layout:

````markdown
# Harness compatibility matrix

Single source of truth for which (asset-kind × harness) pairs are supported and
how each is projected. As of v3.0.0 Phase A this doc covers the **`agent`
(subagent) kind only**; the legacy multi-kind grid returns in Phase B alongside
the adapters. A parity test (`tests/test_subagent_matrix.py`) fails if this doc
and the catalog disagree.

## Mechanisms

<!-- paste the trimmed v1 Mechanisms bullets here: symlink, translate,
     config_file, config_file+folder, dual-symlink, unsupported (gap),
     unsupported (by design) -->
- **unknown** — no public evidence of a subagent concept surfaced within the
  time-boxed search. Distinct from "unsupported (by design)": absence of
  evidence, not evidence of absence.

## Subagent (agent kind) support — all harnesses

This table is the v3.0.0 Phase A deliverable: the `agent` (subagent) verdict for
every harness in the catalog (`src/agent_toolkit_cli/skill_agents.py`, excluding
the synthetic `universal` entry). It is the contract Phase B implements against —
each `supported` row (mechanism = `symlink`/`translate`/`config_file`/`dual-symlink`)
becomes one adapter behaviour. Guarded by `tests/test_subagent_matrix.py`.

| Harness | Verdict | Mechanism | User path / Project path | Format (required/forbidden fields) | Citation |
|---|---|---|---|---|---|
<!-- one row per harness, merged from docs/agent-toolkit/research/subagent-fragments/batch-*.md -->
````

Then paste the rows from every `batch-*.md` fragment, sorted alphabetically by
harness name, into the table. Each row must match the parity-test row shape
(harness in backticks, six pipe-delimited columns).

- [ ] **Step 2: Run the parity test**

Run: `uv run pytest tests/test_subagent_matrix.py -v`
Expected: PASS — all three tests green. If `test_all_catalog_harnesses_present`
fails with "missing", a fragment row was dropped or its harness name is
misspelled; if "extra", a row names a harness not in the catalog. If
`test_supported_rows_have_mechanism_path_citation` fails, a `supported` row is
missing its mechanism/path/citation — go back to that batch's fragment and fill
it (or downgrade the verdict to `unsupported (gap)` / `unknown` with a reason).

- [ ] **Step 3: Run the full suite to confirm no regression**

Run: `uv run pytest -q`
Expected: PASS. The new `tests/test_subagent_matrix.py` goes green once the doc
exists with the section; no legacy parity test is present on this branch (it was
removed in the strip-back along with the doc), so there is nothing to regress.

- [ ] **Step 4: Commit**

```bash
git add docs/agent-toolkit/harness-matrix.md
git commit -m "docs(matrix): all-harness subagent support table (Phase A)"
```

---

## Task 5: Summarise the supported-harness set

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md` (a short summary block at the top of the new section)

Phase B needs the "what's actually supported" headline at a glance. Derive it
from the assembled table — do not hand-maintain a second list.

- [ ] **Step 1: Generate the verdict tally from the table**

Run:
```bash
python - <<'PY'
import re, pathlib, collections
doc = pathlib.Path("docs/agent-toolkit/harness-matrix.md").read_text()
sec = doc.split("## Subagent (agent kind) support — all harnesses", 1)[1]
sec = re.split(r"^## ", sec, maxsplit=1, flags=re.MULTILINE)[0]
row = re.compile(r"^\|\s*`([a-z][a-z0-9-]*)`\s*\|([^|]+)\|")
tally = collections.Counter()
supported = []
for line in sec.splitlines():
    m = row.match(line.strip())
    if not m:
        continue
    h, verdict = m.group(1), m.group(2).strip().lower()
    if verdict.startswith(("symlink", "translate", "config_file", "dual-symlink")):
        tally["supported"] += 1; supported.append(h)
    elif verdict.startswith("unsupported (gap)"):
        tally["gap"] += 1
    elif verdict.startswith("unsupported (by design)"):
        tally["by design"] += 1
    elif verdict.startswith("unknown"):
        tally["unknown"] += 1
    else:
        tally["UNCLASSIFIED"] += 1
print("tally:", dict(tally))
print("supported harnesses:", sorted(supported))
PY
```
Expected: a tally with no `UNCLASSIFIED` entries and a sorted list of supported harnesses.

- [ ] **Step 2: Paste the tally as a summary block**

Immediately under the new section's intro paragraph (before the table), add:

```markdown
**Summary (Phase A):** N supported · N unsupported (gap) · N unsupported (by design) · N unknown.
**Supported set (Phase B work surface):** `claude-code`, `codex`, … (alphabetical).
```

Fill `N` and the supported set from Step 1's output (real numbers — no placeholders).

- [ ] **Step 3: Re-run the parity test (summary block must not break parsing)**

Run: `uv run pytest tests/test_subagent_matrix.py -v`
Expected: PASS. The summary lines start with `**` not `` | ` `` so `_ROW_RE`
ignores them; if a test now sees the summary line as a row, the `**Supported
set...`** line contains backtick-wrapped names — reword it so backticked names
are not at line start after a leading `|` (they aren't, since the line starts
with `**`), or move the supported list onto a bullet list instead of one line.

- [ ] **Step 4: Commit**

```bash
git add docs/agent-toolkit/harness-matrix.md
git commit -m "docs(matrix): Phase A verdict tally + supported-harness set"
```

---

## Task 6: File the v3.0.0 epic GitHub issue

**Files:**
- None (creates a GitHub issue via `gh`)

The issue is the second Phase A deliverable: the epic tracking surface for Phase B.

- [ ] **Step 1: Confirm `gh` is authed and the repo is correct**

Run: `gh repo view --json nameWithOwner -q .nameWithOwner && gh auth status`
Expected: prints the `agent-toolkit-cli` repo slug and "Logged in". If not authed, stop and ask the user to run `! gh auth login`.

- [ ] **Step 2: Draft the issue body referencing the merged matrix**

Write the body to a temp file (avoids shell-quoting issues), filling the tally
and supported set from Task 5 Step 1:

```bash
cat > /tmp/v3-epic-issue.md <<'EOF'
## v3.0.0 — Refold the `agent` (subagent) asset kind

Reintroduce the `agent` (subagent-definition) kind that v1 had and the
strip-back removed, wired for every harness the compatibility table marks
supported, plus the left-hand kind selector in the TUI.

### Phase A — Research (this issue's backbone, DONE when filed)
- [x] All-harness subagent support table in `docs/agent-toolkit/harness-matrix.md`
  (section "Subagent (agent kind) support — all harnesses"), parity-tested by
  `tests/test_subagent_matrix.py`.
- Summary: <N supported / N gap / N by design / N unknown>.
- Supported set (Phase B work surface): <alphabetical list from the table>.

### Phase B — Implementation (separate plan, post-research)
- [ ] `agent` projection adapters — one per supported cell (Claude symlink;
  Codex/OpenCode/Gemini translate; Pi dual-symlink; plus any new supported harness).
- [ ] Generalize install/lock/paths to a `kind` dimension (`skill` | `agent`).
  **Open:** generalize-in-place vs parallel `agent_*` modules — decide in the
  Phase B plan; the lockfile gains a `kind` discriminator (major-bump trigger if
  it breaks vercel-labs/skills lock readers).
- [ ] CLI: full `agent` verb set mirroring `skill` (`add`, `install`,
  `uninstall`, `remove`, `import`, `list`, `status`, `update`, `push`, `reset`)
  + `doctor` learning the `agent` kind. **`agent import` is in scope**
  (read_only library reconstruction, monorepo parent-symlink, `--latest`).
  **Open:** parallel `agent` group vs `--kind` flag.
- [ ] TUI `KindsSidebar` — left-hand rail switching Skills / Agents; other kinds
  defined-but-dormant.

### Non-goals (v3.0.0)
command / hook / plugin / mcp / pi-extension kinds. One kind per major version.

Design spec: `docs/superpowers/specs/2026-05-27-v3-agents-refold-design.md`
Phase A plan: `docs/superpowers/plans/2026-05-27-v3-agents-refold-phase-a-research.md`
EOF
```

Edit `/tmp/v3-epic-issue.md` to replace the three `<...>` placeholders with the
real tally/supported set from Task 5 Step 1.

- [ ] **Step 3: Create the issue**

Run:
```bash
gh issue create \
  --title "v3.0.0: refold the agent (subagent) asset kind" \
  --body-file /tmp/v3-epic-issue.md \
  --label enhancement
```
Expected: prints the new issue URL. If the `enhancement` label doesn't exist,
re-run without `--label`. Capture the issue number for the next step.

- [ ] **Step 4: Cross-link the issue number back into the matrix section**

In `harness-matrix.md`'s new section intro, add: `Tracked in #<issue-number>.`
Then:

```bash
git add docs/agent-toolkit/harness-matrix.md
git commit -m "docs(matrix): link v3.0.0 epic issue #<issue-number> from subagent table"
```

---

## Task 7: Open the PR for Phase A

**Files:**
- None (PR creation)

Phase A is research + docs + a test — it merges as a self-contained PR. Branch is `spec/v3-agents-refold` (already created during brainstorming; confirm before pushing).

- [ ] **Step 1: Confirm branch and that nothing landed on main under us**

Run: `git branch --show-current && git log --oneline -1 origin/main 2>/dev/null`
Expected: current branch is `spec/v3-agents-refold` (NOT `main`). If on `main`, create the branch first: `git switch -c spec/v3-agents-refold`. (Per session memory: a long session can move `main` under you — verify before pushing.)

- [ ] **Step 2: Push and open the PR**

Run:
```bash
git push -u origin spec/v3-agents-refold
gh pr create --fill --base main \
  --title "v3.0.0 Phase A: all-harness subagent support matrix + epic issue"
```
Expected: prints the PR URL. If `git push` reports the branch is up to date but
commits are ahead of origin, fall back to `git push origin spec/v3-agents-refold`
(per session memory: a "clean" report can hide local commits ahead of origin).

- [ ] **Step 3: Confirm CI / parity test green on the PR**

Run: `gh pr checks --watch` (or `gh run list --branch spec/v3-agents-refold -L 3`)
Expected: the parity test (`tests/test_subagent_matrix.py`) and full suite pass.

---

## Self-review against the spec

**Spec coverage:**
- Spec "Phase A deliverable: refreshed harness-matrix.md with complete agent row covering all ~54 harnesses" → Tasks 3–4 (research → assembled 54-row table). ✓
- Spec "citation-grade … current-upstream citation for every supported cell" → Task 2 brief mandates current `file:line`/URL; Task 1 test enforces non-empty citation on supported rows. ✓
- Spec "winnow-then-deep-dive, batched by family, re-verifying ALL 54 incl. v1's 5" → Task 2 two-stage protocol; Task 3 Step 4 re-verifies the 5 baselines with explicit delta capture. ✓
- Spec "output contract = matrix fragments assembled by orchestrator to avoid races" → Task 2 strict output contract; Task 3 persists fragments; Task 4 single-writer assembly. ✓
- Spec "unknowns policy: time-box, mark unknown — no public evidence found" → Task 2 brief + new `unknown` verdict in Task 1 test vocabulary. ✓
- Spec "GitHub issue capturing the v3.0.0 epic with the matrix as backbone, listing the supported-harness set as the Phase B work surface" → Tasks 5 (supported set) + 6 (issue). ✓
- Spec Phase B items (adapters, install/lock kind-generalization, TUI sidebar, CLI agent verbs incl. import, open decisions) → captured as **unchecked** Phase B section in the issue (Task 6 Step 2), NOT as executable tasks here — correct, since Phase B is a separate plan per the approved scope decision. ✓
- Spec "parity test … reintroduce it" → Task 1 creates `tests/test_subagent_matrix.py` (a new all-harness test). The v1 `tests/test_harness_matrix.py` and the matrix doc were both deleted in the strip-back (commit `04aed66`, #164) and exist only at tag `v1.0.0`; Task 4 recreates the doc fresh, Phase-A-scoped. The legacy 5-column grid + its test return in Phase B with the adapters. ✓

**Placeholder scan:** No "TBD"/"implement later". The only intentional fill-ins
are real data the engineer computes in-step (the verdict tally `N`s in Task 5,
the supported set, the issue number) — each has an exact command producing the
value before it's pasted. No code step lacks code.

**Type/name consistency:** `_SECTION_HEADING` string "## Subagent (agent kind)
support — all harnesses" is identical in the test (Task 1), the doc section
(Task 4), and the tally script (Task 5). The catalog accessor `skill_agents.AGENTS`
(a `dict[str, AgentConfig]`, 54 names after dropping `universal`) was verified
against the live module during plan-writing and is used identically in the test
and the partition check (Task 3 Step 1).
Verdict vocabulary `_VERDICTS` (Task 1) matches the brief's verdict list (Task 2)
and the tally classifier (Task 5).

**Gap found and fixed during review:** The tally script (Task 5) and the parity
test (Task 1) must use the SAME verdict-prefix classification or the summary
could disagree with the test. Both now use the prefixes
`symlink`/`translate`/`config_file`/`dual-symlink` for "supported" — consistent.
