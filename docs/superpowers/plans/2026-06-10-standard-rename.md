# Rename `general`/`universal` → `standard` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full rename of the convergence terminology — token strings, internal identifiers, TUI keys/labels, CLI text, docs — from `universal`/`general-*` to `standard`/`standard-*`, with a one-cycle deprecation alias layer for old CLI spellings.

**Architecture:** One atomic token-string rename commit (catalog keys + every quoted literal in src/ and tests/), then a TDD'd boundary-normalization alias layer (`DEPRECATED_TOKEN_ALIASES` + `resolve_agent_token()` in `skill_agents.py`, wired into the five CLI parse boundaries), then a mechanical internal-identifier rename, an arch-guard test, and a docs sweep. **No lock or disk migration** — locks store no agent tokens and no `general*`/`universal*` paths exist on disk (spec § Premise correction).

**Tech Stack:** Python 3.12, Click, Textual, pytest. Run tests with `uv run pytest`.

**Worker notes:**
- Spec: `docs/superpowers/specs/2026-06-10-standard-rename-design.md`. Issue: #350.
- The pre-commit schema-check hook is known-broken (aborts on a removed `--toolkit-repo` option); `--no-verify` is sanctioned when it is the only failure.
- `tests/test_global_install.py::test_empty_machine_is_empty` fails locally only (global inventory ignores `home=`); it is green on CI and not caused by this work.
- Every commit carries a `Device: <hostname -s>` trailer.

---

### Task 1: Token-string rename sweep (atomic)

Rename the three live token strings everywhere they appear as *quoted literals*:
`"universal"` → `"standard"`, `"general-skill"` → `"standard-skill"`,
`"general-agent"` → `"standard-agent"`. Identifiers (`is_universal`,
`show_in_universal_list`, `get_universal_agents`, `general_harness_name`) are
Task 3 — do NOT touch them here. The suite is red mid-task and green at commit.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_agents.py:492-516`
- Modify: `src/agent_toolkit_cli/skill_install.py:57`
- Modify: `src/agent_toolkit_cli/agent_install.py:39-41`
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py:165-167,200-220`
- Modify: `src/agent_toolkit_cli/commands/skill/list_cmd.py:53-58`
- Modify: `src/agent_toolkit_tui/skill_state.py:34`
- Modify: `src/agent_toolkit_tui/column_info.py:49-50,74`
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py:339`
- Modify (sweep): every other quoted occurrence in `src/` and `tests/`

- [ ] **Step 1: Rename the three AGENTS catalog entries** (`skill_agents.py:492-516`)

```python
    "standard": AgentConfig(
        name="standard",
        display_name="Standard",
        skills_dir=".agents/skills",
        global_skills_dir=XDG_CONFIG / "agents/skills",
        show_in_universal_list=False,
        detect_installed=lambda: False,
    ),
    "standard-skill": AgentConfig(
        name="standard-skill",
        display_name="Standard (skills)",
        skills_dir=".agents/skills",
        global_skills_dir=XDG_CONFIG / "agents/skills",
        show_in_universal_list=False,
        detect_installed=lambda: False,
    ),
    "standard-agent": AgentConfig(
        name="standard-agent",
        display_name="Standard (agents)",
        skills_dir=".agents/agents",
        global_skills_dir=XDG_CONFIG / "agents/agents",
        show_in_universal_list=False,
        detect_installed=lambda: False,
        subagent_mechanism="none",  # synthetic — not a real installable harness
    ),
```

(`show_in_universal_list` keeps its old spelling until Task 3.)

- [ ] **Step 2: Synthetic-name frozensets**

`skill_install.py:57`:
```python
_SKILL_SYNTHETIC_NAMES: frozenset[str] = frozenset({"standard", "standard-skill"})
```

`agent_install.py:39-41` (comment + set):
```python
# Note: no "standard" bundle — that's skill-only. "standard-agent" mirrors
# "standard-skill" from the skill facade.
_AGENT_SYNTHETIC_NAMES: frozenset[str] = frozenset({"standard-agent"})
```

- [ ] **Step 3: Skill CLI group** (`commands/skill/__init__.py`)

Epilog lines 165-167:
```
  # Make it visible to a specific agent (claude-code) or all standard harnesses
  $ agent-toolkit-cli skill install journal --agents claude-code
  $ agent-toolkit-cli skill install journal --agents standard
```

`_resolve_agents` (lines 200-220) — rename literals only (alias wiring is Task 2):
```python
def _resolve_agents(agents_str: str, scope: str) -> tuple[str, ...]:
    """Expand a comma-separated --agents string into a tuple of agent names.

    Special values:
      "standard" → the standard bundle token (creates ~/.agents/skills/<slug>)
      "all"      → every agent detected as installed at the given scope
    """
    if agents_str == "all":
        return tuple(detect_installed_agents())
    parts = [p.strip() for p in agents_str.split(",") if p.strip()]
    # "standard" is a valid token; other names must be in the catalog.
    unknown = [p for p in parts if p != "standard" and p not in AGENTS]
    if unknown:
        raise click.UsageError(f"unknown agent(s): {', '.join(unknown)}")
    synthetic = [p for p in parts if p == "standard-skill"]
    if synthetic:
        raise click.UsageError(
            f"standard-skill is a synthetic catalog entry, not a usable agent token: "
            f"{', '.join(synthetic)}"
        )
    return tuple(parts)
```

- [ ] **Step 4: `list_cmd.py:53-58`**

```python
    if agent is not None and agent != "standard" and agent not in AGENTS:
        raise click.UsageError(f"unknown agent: {agent}")
    if agent == "standard-skill":
        raise click.UsageError(
            "standard-skill is a synthetic catalog entry, not a usable agent token"
        )
```

- [ ] **Step 5: TUI keys and labels**

`skill_state.py:34`:
```python
INTERACTIVE_AGENTS: tuple[str, ...] = ("standard", "claude-code", "pi")
```

`column_info.py:74`: registry key `"universal"` → `"standard"`. Lines 49-50: title
`"General bundle"` → `"Standard bundle"`; replace the `#304 display-only rename`
comment with: `# v3.7 full rename (#350): key and title both say "standard".`

`instruction_grid.py:339`: `f"general {_INFO_GLYPH}"` → `f"standard {_INFO_GLYPH}"`.

- [ ] **Step 6: Sweep every remaining quoted token literal in src/ and tests/**

```bash
grep -rln '"universal"\|'"'"'universal'"'"'\|general-skill\|general-agent' src/ tests/ | while read -r f; do
  sed -i '' \
    -e 's/"universal"/"standard"/g' -e "s/'universal'/'standard'/g" \
    -e 's/general-skill/standard-skill/g' \
    -e 's/general-agent/standard-agent/g' "$f"
done
```

Then verify nothing quoted remains (identifiers like `get_universal_agents` and
`general_harness_name` WILL still match a bare grep — that is expected until Task 3):

```bash
grep -rn '"universal"\|'"'"'universal'"'"'\|general-skill\|general-agent' src/ tests/
```
Expected: no output. Manually eyeball `git diff` for sed collateral (docstrings
reading "the standard bundle" etc. should read naturally; fix wording by hand).

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -x -q`
Expected: PASS (except the known-local `test_empty_machine_is_empty`).

- [ ] **Step 8: Commit**

```bash
git add -A src tests
git commit -m "feat(rename): universal/general-* tokens → standard/standard-* (#350)

Device: $(hostname -s)"
```

---

### Task 2: Deprecation alias layer (TDD)

**Files:**
- Create: `tests/test_token_aliases.py`
- Modify: `src/agent_toolkit_cli/skill_agents.py` (below `UnknownAgentError`)
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py` (`_resolve_agents`)
- Modify: `src/agent_toolkit_cli/commands/skill/list_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/skill/_common.py:38-44` (`validate_agent_names`)
- Modify: `src/agent_toolkit_cli/commands/agent/install_cmd.py:40-48` (`_resolve_harnesses`)
- Modify: `src/agent_toolkit_cli/commands/agent/uninstall_cmd.py:22-31` (`_resolve_harnesses_for_uninstall`)

(`commands/instructions/install_cmd.py` is deliberately NOT wired: `universal`/
`general-*` were never accepted harness values there, so there is nothing to alias.)

- [ ] **Step 1: Write the failing tests** (`tests/test_token_aliases.py`)

```python
"""Deprecated token aliases (#350): old spellings warn + map for one cycle."""
import pytest

from agent_toolkit_cli.skill_agents import (
    AGENTS,
    DEPRECATED_TOKEN_ALIASES,
    _warned_deprecated,
    resolve_agent_token,
)


@pytest.fixture(autouse=True)
def _reset_warned():
    _warned_deprecated.clear()
    yield
    _warned_deprecated.clear()


@pytest.mark.parametrize("old,new", sorted(DEPRECATED_TOKEN_ALIASES.items()))
def test_alias_maps_old_to_new(old, new):
    assert resolve_agent_token(old) == new


def test_expected_alias_table():
    assert DEPRECATED_TOKEN_ALIASES == {
        "universal": "standard",
        "general-skill": "standard-skill",
        "general-agent": "standard-agent",
        "general-instructions": "standard-instructions",
        "general-pi-extension": "standard-pi-extension",
    }


def test_new_and_unknown_tokens_pass_through():
    assert resolve_agent_token("standard") == "standard"
    assert resolve_agent_token("claude-code") == "claude-code"
    assert resolve_agent_token("nope") == "nope"  # validation stays at callers


def test_warning_printed_once_per_token(capsys):
    resolve_agent_token("universal")
    resolve_agent_token("universal")
    err = capsys.readouterr().err
    assert err.count("deprecated") == 1
    assert "'standard'" in err and "v4" in err


def test_aliased_catalog_targets_exist():
    for new in DEPRECATED_TOKEN_ALIASES.values():
        if new in {"standard-instructions", "standard-pi-extension"}:
            continue  # defensive aliases — these were never catalog entries
        assert new in AGENTS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_token_aliases.py -q`
Expected: FAIL — `ImportError: cannot import name 'DEPRECATED_TOKEN_ALIASES'`.

- [ ] **Step 3: Implement the alias layer** (`skill_agents.py`, after `get_agent`)

```python
# --- Deprecated token aliases (#350) -----------------------------------------
# Old spellings accepted for one cycle with a stderr warning; the whole block
# (table + resolver + call sites) is deleted in v4.
DEPRECATED_TOKEN_ALIASES: dict[str, str] = {
    "universal": "standard",
    "general-skill": "standard-skill",
    "general-agent": "standard-agent",
    "general-instructions": "standard-instructions",
    "general-pi-extension": "standard-pi-extension",
}

_warned_deprecated: set[str] = set()


def resolve_agent_token(name: str) -> str:
    """Map a deprecated agent/harness token to its 'standard' replacement.

    Warns once per old token per process on stderr. Names that are not in the
    alias table pass through unchanged — unknown-token validation stays at the
    callers (UnknownAgentError / click.UsageError).
    """
    new = DEPRECATED_TOKEN_ALIASES.get(name)
    if new is None:
        return name
    if name not in _warned_deprecated:
        _warned_deprecated.add(name)
        print(
            f"warning: '{name}' is deprecated; renamed to '{new}'. "
            f"The old spelling will be removed in v4.",
            file=sys.stderr,
        )
    return new
```

Add `import sys` to the module imports if absent.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_token_aliases.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Wire the five CLI boundaries**

`commands/skill/__init__.py` — import + first line of parsing in `_resolve_agents`:
```python
from agent_toolkit_cli.skill_agents import resolve_agent_token
```
```python
    parts = [resolve_agent_token(p.strip()) for p in agents_str.split(",") if p.strip()]
```
Append to the docstring: `Deprecated spellings ("universal", "general-skill", …)
are aliased with a stderr warning via resolve_agent_token().`

`commands/skill/list_cmd.py` — before the validation block:
```python
    if agent is not None:
        agent = resolve_agent_token(agent)
```

`commands/skill/_common.py` `validate_agent_names`:
```python
def validate_agent_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """Resolve deprecated aliases, then raise UsageError on unknown names."""
    resolved = tuple(resolve_agent_token(n) for n in names)
    for n in resolved:
        if n not in AGENTS:
            raise click.UsageError(f"unknown agent: {n}")
    return resolved
```

`commands/agent/install_cmd.py` `_resolve_harnesses` and
`commands/agent/uninstall_cmd.py` `_resolve_harnesses_for_uninstall` — same
one-line change in each:
```python
        parts = [resolve_agent_token(p.strip()) for p in harnesses_str.split(",") if p.strip()]
```

- [ ] **Step 6: Write the failing CLI integration test** (append to `tests/test_token_aliases.py`)

```python
from agent_toolkit_cli.commands.skill import _resolve_agents


def test_resolve_agents_accepts_deprecated_universal(capsys):
    assert _resolve_agents("universal", "global") == ("standard",)
    assert "deprecated" in capsys.readouterr().err


def test_resolve_agents_accepts_new_token_silently(capsys):
    assert _resolve_agents("standard", "global") == ("standard",)
    assert capsys.readouterr().err == ""


def test_resolve_agents_still_rejects_unknown():
    import click
    with pytest.raises(click.UsageError):
        _resolve_agents("definitely-not-a-harness", "global")


def test_resolve_agents_old_synthetic_spelling_still_rejected():
    import click
    with pytest.raises(click.UsageError, match="synthetic"):
        _resolve_agents("general-skill", "global")  # aliases to standard-skill, then rejected
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_token_aliases.py -q`
Expected: PASS. Then the full suite: `uv run pytest -x -q` → PASS.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_cli tests/test_token_aliases.py
git commit -m "feat(rename): deprecation alias layer for old universal/general-* tokens (#350)

Device: $(hostname -s)"
```

---

### Task 3: Internal identifier rename (mechanical)

**Files:**
- Modify: `src/agent_toolkit_cli/_paths_core.py:22-57`
- Modify (sweep): everywhere `is_universal` / `show_in_universal_list` /
  `get_universal_agents` appear (src/ + tests/)

- [ ] **Step 1: KindBinding field + values** (`_paths_core.py`)

```python
    standard_harness_name: str  # "standard-skill" | "standard-agent"
```
and in the four bindings: `standard_harness_name="standard-skill"`,
`="standard-instructions"`, `="standard-agent"`, `="standard-pi-extension"`.
(The field is currently consumed nowhere outside this module — renamed rather
than deleted because #351's per-kind info panel will consume it.)

- [ ] **Step 2: Identifier sweep**

```bash
grep -rln 'is_universal\|show_in_universal_list\|get_universal_agents\|general_harness_name' src/ tests/ | while read -r f; do
  sed -i '' \
    -e 's/show_in_universal_list/show_in_standard_list/g' \
    -e 's/get_universal_agents/get_standard_agents/g' \
    -e 's/is_universal/is_standard/g' \
    -e 's/general_harness_name/standard_harness_name/g' "$f"
done
```

Update the `get_standard_agents` docstring in `skill_agents.py` by hand:
```python
def get_standard_agents() -> list[str]:
    """Agents whose skillsDir == '.agents/skills', excluding the synthetic
    'standard' pseudo-entry. (Renamed from getUniversalAgents/agents.ts.)"""
```

- [ ] **Step 3: Comment/docstring wording sweep**

```bash
grep -rni 'universal' src/ --include="*.py"
```
For each remaining hit (comments/docstrings only at this point), reword to
"standard" where it names the concept; keep historical references (e.g. "#304",
"agents.ts") intact. Expected after fixes: only historical-context mentions remain.

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -x -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A src tests
git commit -m "refactor(rename): is_universal/show_in_universal_list/get_universal_agents/general_harness_name → standard identifiers (#350)

Device: $(hostname -s)"
```

---

### Task 4: Arch guard — no old tokens outside the alias table

**Files:**
- Modify: `tests/test_subagent_matrix.py` (sets at :58 and :241 were already
  renamed by Task 1's sweep — verify, don't re-edit)
- Create: `tests/test_no_legacy_tokens.py`

- [ ] **Step 1: Write the failing-or-passing guard test**

```python
"""Arch guard (#350): old token spellings must not reappear in src/.

The only sanctioned host is the DEPRECATED_TOKEN_ALIASES block in
skill_agents.py (deleted in v4 along with this allowance).
"""
import re
from pathlib import Path

OLD_TOKEN = re.compile(
    r"['\"](universal|general-skill|general-agent|general-instructions|general-pi-extension)['\"]"
)
SRC = Path(__file__).resolve().parents[1] / "src"


def _alias_block(text: str) -> tuple[int, int]:
    """Line range (1-based, inclusive) of the DEPRECATED_TOKEN_ALIASES literal."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines, 1) if "DEPRECATED_TOKEN_ALIASES" in l)
    end = next(i for i, l in enumerate(lines[start:], start + 1) if l.strip() == "}")
    return start, end


def test_no_old_tokens_in_src_outside_alias_table():
    offenders: list[str] = []
    for py in sorted(SRC.rglob("*.py")):
        text = py.read_text()
        allowed = _alias_block(text) if py.name == "skill_agents.py" else (0, -1)
        for i, line in enumerate(text.splitlines(), 1):
            if OLD_TOKEN.search(line) and not (allowed[0] <= i <= allowed[1]):
                offenders.append(f"{py.relative_to(SRC)}:{i}: {line.strip()}")
    assert not offenders, "old token spellings outside the alias table:\n" + "\n".join(offenders)
```

- [ ] **Step 2: Run the guard**

Run: `uv run pytest tests/test_no_legacy_tokens.py -q`
Expected: PASS. If it FAILS, each offender line is a Task 1/3 straggler — fix it
(rename the literal, or reword the comment to drop the quoted token) and re-run.

- [ ] **Step 3: Verify the renamed synthetic sets in `test_subagent_matrix.py`**

Run: `grep -n "standard" tests/test_subagent_matrix.py | head`
Expected: lines 58 and 241 now read `{"standard", "standard-skill", "standard-agent"}`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_no_legacy_tokens.py
git commit -m "test(rename): arch guard — no legacy universal/general-* tokens outside alias table (#350)

Device: $(hostname -s)"
```

---

### Task 5: Docs sweep + deprecation notes

**Files:**
- Modify: `docs/agent-toolkit/cli.md:20,92`
- Modify: `docs/index.md:34`
- Modify: `docs/agent-toolkit/harness-matrix.md:55,177,278-279`

- [ ] **Step 1: `cli.md`**

Line 20: `…filters to skills currently symlinked into that agent (or the
\`standard\` token)`. Line 92: `The 55-agent catalog (skillsDir ==
.agents/skills = standard)`. Add once, near the first mention:

> **Terminology:** *standard* — formerly "general" (v3), earlier "universal"
> (pre-v3). The old token spellings still work for one cycle with a deprecation
> warning and are removed in v4.

- [ ] **Step 2: `index.md:34`**

`Universal agents (…)` → `Standard harnesses (codex, opencode, gemini-cli, +11
more whose skillsDir == .agents/skills)`; `Non-universal agents` →
`Non-standard harnesses`. Add the same terminology note as Step 1.

- [ ] **Step 3: `harness-matrix.md`**

Line 55 `the synthetic universal entry` → `the synthetic standard entry`.
Lines 177 and 278-279: `per-kind "general" column/set` → `per-kind "standard"
column/set`. Add the terminology note once at the top of the per-kind section.
Historical CHANGELOG entries and committed specs/plans are NOT rewritten.

- [ ] **Step 4: Grep checkpoint + commit**

```bash
grep -rni "universal\|\"general\"\|'general'\|general-skill\|general-agent" docs/agent-toolkit/cli.md docs/index.md docs/agent-toolkit/harness-matrix.md
```
Expected: only the three terminology notes (which legitimately mention the old
names) remain.

```bash
git add docs/agent-toolkit/cli.md docs/index.md docs/agent-toolkit/harness-matrix.md
git commit -m "docs(rename): general/universal → standard terminology + deprecation notes (#350)

Device: $(hostname -s)"
```

---

### Task 6: Follow-up issue + final verification

- [ ] **Step 1: File the v4 alias-removal follow-up**

```bash
gh issue create \
  --title "v4: remove deprecated universal/general-* token aliases (#350 follow-up)" \
  --body "Delete DEPRECATED_TOKEN_ALIASES + resolve_agent_token() call sites (skill_agents.py and the five CLI boundaries), the skill_agents.py allowance in tests/test_no_legacy_tokens.py, and the alias tests in tests/test_token_aliases.py. Old spellings then raise UnknownAgentError/UsageError. Breaking — v4.0.0 only." \
  --milestone v4.0.0
```
If the `v4.0.0` milestone doesn't exist, create without `--milestone` and note
the v4 constraint in the body (already present).

- [ ] **Step 2: Full suite + smoke**

Run: `uv run pytest -q`
Expected: PASS (modulo the known-local `test_empty_machine_is_empty`).

Smoke (from the repo root):
```bash
uv run agent-toolkit-cli skill list -a universal 2>&1 | head -3   # warns, then lists
uv run agent-toolkit-cli skill list -a standard | head -3          # silent, lists
```

- [ ] **Step 3: Verify no stray commits / push via PR**

The runner opens a PR per its own flow (`/aj-run` worktree + conventional PR
title `feat(rename): …` so release-please cuts a minor).
