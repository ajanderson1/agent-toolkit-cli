# Remove deprecated `universal`/`general-*` token aliases (#356) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the one-cycle deprecation alias layer introduced by #350 so old token spellings (`universal`, `general-skill`, `general-agent`) raise unknown-token errors instead of warning + mapping.

**Architecture:** Pure deletion. The alias machinery is one self-contained block in `skill_agents.py` plus five call sites that wrap a raw token in `resolve_agent_token(...)` before each site's *existing* unknown-token guard. Remove the wrapper everywhere and the old spellings flow straight into that guard and get rejected. Two dedicated test files change (one deleted, one's allowance removed), and one doc line moves to past tense.

**Tech Stack:** Python 3, Click CLI, pytest, `uv run`, ruff, mypy. macOS dev host (BSD sed) — a Linux worker must adapt `sed` forms; this plan uses Edit-tool string replacements, not sed, so no adaptation is needed.

---

## File structure

| File | Change |
|---|---|
| `src/agent_toolkit_cli/skill_agents.py` | Delete L531–560 (alias comment + table + `_warned_deprecated` + `resolve_agent_token`); delete L11 `import sys` |
| `src/agent_toolkit_cli/commands/skill/__init__.py` | Drop `resolve_agent_token` import (L16); unwrap `_resolve_agents` body (L212); fix docstring (L207–208) |
| `src/agent_toolkit_cli/commands/skill/_common.py` | Drop `resolve_agent_token` import (L10); unwrap `validate_agent_names` (L43) |
| `src/agent_toolkit_cli/commands/skill/list_cmd.py` | Drop `resolve_agent_token` import (L8); remove the resolve line (L54) |
| `src/agent_toolkit_cli/commands/agent/_common.py` | Drop deferred `resolve_agent_token` import (L36); unwrap `parse_harness_tokens` (L38); reword comment (L19–22) |
| `tests/test_token_aliases.py` | Delete entire file |
| `tests/test_no_legacy_tokens.py` | Remove the `DEPRECATED_TOKEN_ALIASES` allowance; guard now enforces zero old spellings |
| `tests/test_token_removal.py` | **Create** — pins the post-removal behaviour (old spellings raise) |
| `tests/test_cli/test_agent_cli_standard.py` | Reword stale "#350 aliases resolve first" rationale (L104–105); tests stay green |
| `docs/agent-toolkit/cli.md` | Update terminology note (L22) to past tense |
| `docs/agent-toolkit/harness-matrix.md` | Update terminology note (L203, byte-identical to cli.md:22) to past tense |

> All line numbers verified against `main` on 2026-06-12. If they have drifted, re-`grep -rn "resolve_agent_token\|DEPRECATED_TOKEN_ALIASES" src/` to relocate before editing — the *symbols* are the anchors, not the numbers.

---

## Task 1: Pin the post-removal behaviour (RED — written before deletion)

This is the regression that proves the break. It must **fail today** (old spellings currently warn-and-map, returning a mapped token instead of raising) and **pass after Task 2**.

**Files:**
- Create: `tests/test_token_removal.py`

- [ ] **Step 1: Write the failing test**

```python
"""#356: deprecated token aliases are removed — old spellings now raise.

Pins the hard break shipped as v4.0.0. Before #356 these spellings warned on
stderr and mapped to their 'standard' equivalents; after removal they are
unknown tokens and hit each caller's existing unknown-token guard.
"""
import click
import pytest

from agent_toolkit_cli.commands.skill import _resolve_agents
from agent_toolkit_cli.commands.agent._common import parse_harness_tokens


def test_resolver_symbols_are_gone():
    """The unambiguous RED anchor: these symbols exist pre-removal, gone after."""
    import agent_toolkit_cli.skill_agents as sa
    assert not hasattr(sa, "resolve_agent_token")
    assert not hasattr(sa, "DEPRECATED_TOKEN_ALIASES")
    assert not hasattr(sa, "_warned_deprecated")


# NOTE on RED honesty (verified live 2026-06-12): not every old spelling flips
# from pass→raise. `universal` and `general-agent` currently *map* (no raise) via
# _resolve_agents, so those are genuine REDs. `general-skill` already raises today
# because it maps to the synthetic `standard-skill` and hits the synthetic guard —
# it raises both before AND after (the *reason* changes, not the outcome). The
# asserts below are still correct post-removal; the genuine behaviour-flip is
# proven by `universal`/`general-agent` + the symbols test.
@pytest.mark.parametrize("token", ["universal", "general-skill", "general-agent"])
def test_skill_agents_old_spellings_now_raise(token):
    with pytest.raises(click.UsageError):
        _resolve_agents(token, "global")


@pytest.mark.parametrize("token", ["universal", "general-agent"])
def test_harness_old_spellings_now_raise(token):
    with pytest.raises(click.UsageError):
        parse_harness_tokens(token)


def test_old_spelling_emits_no_deprecation_warning(capsys):
    """Post-removal there is no warn-then-raise; just a clean unknown-token error."""
    with pytest.raises(click.UsageError):
        _resolve_agents("universal", "global")
    assert "deprecated" not in capsys.readouterr().err


def test_new_tokens_still_work_silently(capsys):
    assert _resolve_agents("standard", "global") == ("standard",)
    assert capsys.readouterr().err == ""


def test_unknown_token_still_raises():
    with pytest.raises(click.UsageError):
        _resolve_agents("definitely-not-a-harness", "global")
```

- [ ] **Step 2: Run it — confirm RED**

Run: `uv run pytest tests/test_token_removal.py -v`
Expected (verified live against `main` 2026-06-12):
- `test_resolver_symbols_are_gone` → **FAIL** (symbols still present) — the clean RED anchor.
- `test_skill_agents_old_spellings_now_raise[universal]` and `[general-agent]` → **FAIL** (currently map, no raise).
- `test_harness_old_spellings_now_raise[universal]` → **FAIL** (currently maps).
- `test_old_spelling_emits_no_deprecation_warning` → **FAIL** (warning IS printed today + no raise).
- `test_skill_agents_old_spellings_now_raise[general-skill]` and `test_harness_old_spellings_now_raise[general-agent]` → already PASS (they raise via the synthetic guard even today — see the NOTE above; not behaviour-flips but correct).
- `test_new_tokens_still_work_silently`, `test_unknown_token_still_raises` → already PASS.

At least 4 FAILs confirm the test genuinely detects the pre-removal behaviour. If `test_resolver_symbols_are_gone` does NOT fail, the alias block was already removed — stop and reconcile.

- [ ] **Step 3: Commit the RED test**

```bash
git add tests/test_token_removal.py
git commit -m "test(token-aliases): pin post-removal behaviour for #356 (RED)"
```

---

## Task 2: Delete the alias machinery from `skill_agents.py`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_agents.py` (remove L531–560 block + L11 `import sys`)

- [ ] **Step 1: Delete the alias block**

Remove this entire block (currently L531–560, between `get_agent()` and `get_standard_agents()`):

```python
# --- Deprecated token aliases (#350) -----------------------------------------
# Old spellings accepted for one cycle with a stderr warning; the whole block
# (table + resolver + call sites) is deleted in v4.
DEPRECATED_TOKEN_ALIASES: dict[str, str] = {
    "universal": "standard",
    "general-skill": "standard-skill",
    "general-agent": "standard-agent",
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

`get_agent()` and `get_standard_agents()` (the surrounding functions) stay exactly as they are.

- [ ] **Step 2: Delete the now-unused `import sys`**

At the top of the file (L11), `import sys` was the resolver's only consumer. Remove that single line. (Verify nothing else uses `sys`: `grep -n "sys\." src/agent_toolkit_cli/skill_agents.py` must return nothing after the edit.)

- [ ] **Step 3: Confirm RED→partial — symbols gone but call sites still import them**

Run: `uv run pytest tests/test_token_removal.py::test_resolver_symbols_are_gone -v`
Expected: PASS now. But importing `_resolve_agents` will still fail because `skill/__init__.py` imports the deleted symbol — that is fixed in Task 3. Do not commit yet.

---

## Task 3: Unwrap the five call sites

Each call site loses its `resolve_agent_token` import and passes the raw token to its existing guard. Tasks 3a–3d, then verify.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/skill/_common.py`
- Modify: `src/agent_toolkit_cli/commands/skill/list_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/agent/_common.py`

- [ ] **Step 3a: `skill/__init__.py`**

Remove `resolve_agent_token` from the import (L16 area). The import currently reads (find the actual block — it imports several names from `skill_agents`):

```python
from agent_toolkit_cli.skill_agents import (
    ...,
    resolve_agent_token,
    ...,
)
```

Delete only the `resolve_agent_token,` line; keep the other imported names (`AGENTS`, etc.).

In `_resolve_agents` (L212), change:

```python
    parts = [resolve_agent_token(p.strip()) for p in agents_str.split(",") if p.strip()]
```

to:

```python
    parts = [p.strip() for p in agents_str.split(",") if p.strip()]
```

Update the docstring (L207–208), replacing:

```python
    Deprecated spellings (universal, general-*) are aliased with a stderr
    warning via resolve_agent_token().
```

with:

```python
    Old spellings (universal, general-*) are no longer recognised (#356) and
    fall through to the unknown-token guard below.
```

- [ ] **Step 3b: `skill/_common.py`**

Remove `resolve_agent_token` from the import block (L8–11):

```python
from agent_toolkit_cli.skill_agents import (
    AGENTS,
    resolve_agent_token,
)
```

becomes:

```python
from agent_toolkit_cli.skill_agents import AGENTS
```

In `validate_agent_names` (L41–47), change:

```python
def validate_agent_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """Resolve deprecated aliases, then raise UsageError on unknown names."""
    resolved = tuple(resolve_agent_token(n) for n in names)
    for n in resolved:
        if n not in AGENTS:
            raise click.UsageError(f"unknown agent: {n}")
    return resolved
```

to:

```python
def validate_agent_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """Raise UsageError on names not in the catalog."""
    for n in names:
        if n not in AGENTS:
            raise click.UsageError(f"unknown agent: {n}")
    return names
```

- [ ] **Step 3c: `skill/list_cmd.py`**

Change the import (L8):

```python
from agent_toolkit_cli.skill_agents import AGENTS, resolve_agent_token
```

to:

```python
from agent_toolkit_cli.skill_agents import AGENTS
```

Remove the resolve line (L53–54):

```python
    if agent is not None:
        agent = resolve_agent_token(agent)
    if agent is not None and agent != "standard" and agent not in AGENTS:
```

becomes (delete the two-line `if agent is not None: resolve` block; the unknown-check below it stays):

```python
    if agent is not None and agent != "standard" and agent not in AGENTS:
```

- [ ] **Step 3d: `agent/_common.py`**

Change the deferred import (L36):

```python
    from agent_toolkit_cli.skill_agents import AGENTS, resolve_agent_token
```

to:

```python
    from agent_toolkit_cli.skill_agents import AGENTS
```

Change the body (L38):

```python
    parts = [resolve_agent_token(p.strip()) for p in harnesses_str.split(",") if p.strip()]
```

to:

```python
    parts = [p.strip() for p in harnesses_str.split(",") if p.strip()]
```

Reword the comment (L19–22) — drop the alias-resolution claim:

```python
# Synthetic catalog names (#361 AC7): real AGENTS entries that are NOT
# installable harnesses for the agent asset type. Rejected with an explicit
# UsageError instead of the previous silent no-op. #350 aliases resolve
# first, so e.g. general-skill is rejected the same way.
```

becomes:

```python
# Synthetic catalog names (#361 AC7): real AGENTS entries that are NOT
# installable harnesses for the agent asset type. Rejected with an explicit
# UsageError instead of the previous silent no-op.
```

Also update the `parse_harness_tokens` docstring line (L29) "resolves #350 aliases, " — remove that clause so the docstring no longer claims alias resolution:

```python
    Shared by install and uninstall: resolves #350 aliases, rejects the
```

becomes:

```python
    Shared by install and uninstall: rejects the
```

- [ ] **Step 4: Run the removal regression — confirm GREEN**

Run: `uv run pytest tests/test_token_removal.py -v`
Expected: ALL PASS. Symbols gone, old spellings raise, new tokens silent, unknown still raises.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_agents.py \
        src/agent_toolkit_cli/commands/skill/__init__.py \
        src/agent_toolkit_cli/commands/skill/_common.py \
        src/agent_toolkit_cli/commands/skill/list_cmd.py \
        src/agent_toolkit_cli/commands/agent/_common.py
git commit -m "fix(agents)!: remove deprecated universal/general-* token aliases (#356)

Old spellings now raise UnknownAgentError/UsageError instead of warning +
mapping. Completes the #350 deprecation cycle.

BREAKING CHANGE: 'universal', 'general-skill', 'general-agent' are no longer
accepted as agent/harness tokens — use 'standard' / 'standard-skill' /
'standard-agent'. This is the v4.0.0 trigger.

Release-As: 4.0.0"
```

> **Why `!` + `Release-As: 4.0.0` (critical-review finding, 2026-06-12):** a bare
> `fix:` on this repo makes release-please open a *patch* (3.9.x) release PR — proven
> by history (`7c74c0b fix:` cut 3.5.2). Merging that patch would ship the hard break
> with no major-version signal. The `!` marks the breaking change and `Release-As:
> 4.0.0` forces the major cut *with* the removal. The `BREAKING CHANGE:` footer feeds
> release-please's CHANGELOG breaking-changes section (so no separate CHANGELOG edit is
> needed — release-please generates it from this footer). **The `Release-As:` /
> `BREAKING CHANGE:` footer must survive squash-merge** — this repo squash-merges, so
> release-please reads the **PR title + squash body**, not intermediate commits (this is
> the documented "flow PR titles skip release-please" trap). Concretely: the **PR title**
> must be `fix(agents)!: remove deprecated …` (the `!` carries the major bump) and the
> **squash-merge body** must contain both the `BREAKING CHANGE:` footer (release-please
> generates the CHANGELOG breaking-changes section from it) and `Release-As: 4.0.0`.
> Verified precedent on this repo: `09852da` pinned its version via `Release-As: 3.6.2`
> in the squash body. `release-please-config.json` is `release-type: python`, which
> honours `!` / `BREAKING CHANGE:` / `Release-As:`.

---

## Task 4: Retire the old alias tests + tighten the arch guard

**Files:**
- Delete: `tests/test_token_aliases.py`
- Modify: `tests/test_no_legacy_tokens.py`
- Modify: `tests/test_cli/test_agent_cli_standard.py` (reword two now-false comments)

- [ ] **Step 1: Delete the alias contract test**

```bash
git rm tests/test_token_aliases.py
```

Its entire purpose was the alias layer (mapping, warn-once, CLI boundary accept/warn/reject). Task 1's `test_token_removal.py` pins the replacement behaviour.

- [ ] **Step 2: Tighten `test_no_legacy_tokens.py`**

The current guard *allows* old spellings inside the `DEPRECATED_TOKEN_ALIASES` block. That block is gone, so the allowance is dead and must be removed — the guard then enforces **zero** old spellings anywhere in `src/`. Replace the whole file with:

```python
"""Arch guard (#350, hardened by #356): old token spellings must not appear in src/.

#356 removed the DEPRECATED_TOKEN_ALIASES block, so there is no longer any
sanctioned host — zero old spellings allowed anywhere in src/.
"""
import re
from pathlib import Path

OLD_TOKEN = re.compile(
    r"['\"](universal|general-skill|general-agent|general-instructions|general-pi-extension)['\"]"
)
SRC = Path(__file__).resolve().parents[1] / "src"


def test_no_old_tokens_in_src():
    offenders: list[str] = []
    for py in sorted(SRC.rglob("*.py")):
        text = py.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if OLD_TOKEN.search(line):
                offenders.append(f"{py.relative_to(SRC)}:{i}: {line.strip()}")
    assert not offenders, "old token spellings in src/:\n" + "\n".join(offenders)
```

- [ ] **Step 3: Reword the now-false alias rationale in `test_agent_cli_standard.py`**

These two tests feed `general-skill`/`general-agent` through `parse_harness_tokens` (via `_resolve_harnesses` / `_resolve_harnesses_for_uninstall`) and assert `UsageError`. They **stay green** post-removal — the tokens now hit the *unknown-harness* guard instead of the synthetic guard, still `UsageError` (`pytest.raises` doesn't match on message). But their comments claim "#350 aliases resolve first," which is false once aliases are gone. Fix the wording — do NOT touch the assertions or the token list (the tests are correct as-is).

In `test_synthetic_tokens_rejected` (L102–105), change:

```python
def test_synthetic_tokens_rejected():
    """AC7 (review-corrected): ALL synthetic catalog names get an explicit
    UsageError — previously a silent no-op. #350 aliases resolve first, so
    general-skill is rejected the same way."""
```

to:

```python
def test_synthetic_tokens_rejected():
    """AC7 (review-corrected): ALL synthetic catalog names get an explicit
    UsageError — previously a silent no-op. general-skill (an old #350 spelling,
    removed in #356) is now an unknown token and is rejected the same way."""
```

The `test_uninstall_helper_rejects_synthetics` test (L118–125) has no alias-mentioning comment, so it needs no change — but verify its token tuple `("standard-agent", "standard-skill", "general-agent")` still all raise (they do: synthetics + one unknown old spelling).

- [ ] **Step 4: Run the guard + the touched tests**

Run: `uv run pytest tests/test_no_legacy_tokens.py tests/test_cli/test_agent_cli_standard.py -v`
Expected: PASS. (If the guard fails, an old quoted spelling survived a Task-3 edit — grep the offender path:line it reports and remove the quoted token. Note: the `# universal→general rename` comment in `_install_core.py:117` and the `(universal, general-*)` docstring mentions are **unquoted** prose, so the regex — which requires surrounding quotes — does not match them. Only *quoted* `'universal'`/`"general-skill"` etc. trip it. The guard scans `src/` only, so the test-file edit above never affects it.)

- [ ] **Step 5: Commit**

```bash
git add tests/test_no_legacy_tokens.py tests/test_cli/test_agent_cli_standard.py
git commit -m "test(token-aliases): retire alias tests, harden arch guard, reword stale rationale (#356)"
```

---

## Task 5: Update the user-facing docs

**Files:**
- Modify: `docs/agent-toolkit/cli.md:22`
- Modify: `docs/agent-toolkit/harness-matrix.md:203` (byte-identical copy of the same note)

- [ ] **Step 1: Update both terminology notes**

`cli.md:22` and `harness-matrix.md:203` are **byte-identical** (verified via diff 2026-06-12). Both currently read:

```markdown
> **Terminology:** *standard* — formerly "general" (v3), earlier "universal" (pre-v3). The old token spellings still work for one cycle with a deprecation warning and are removed in v4.
```

Change the second sentence to past tense **in both files** (the lines are identical, so the same Edit applies to each):

```markdown
> **Terminology:** *standard* — formerly "general" (v3), earlier "universal" (pre-v3). The old token spellings were removed in v4; they now raise an unknown-token error.
```

> **Why both:** if only `cli.md` is fixed, `harness-matrix.md` keeps telling users the aliases "still work" — a now-false published-docs claim (critical-review finding, 2026-06-12). The arch guard does NOT cover docs, so nothing else catches this.

- [ ] **Step 2: Verify no other copy survives**

Run: `grep -rn "still work for one cycle" docs/`
Expected: **no output** (both copies fixed). If a third copy appears, fix it the same way.

- [ ] **Step 3: Commit**

```bash
git add docs/agent-toolkit/cli.md docs/agent-toolkit/harness-matrix.md
git commit -m "docs: mark universal/general-* token aliases as removed (#356)"
```

---

## Task 6: Full-suite + lint verification

**Files:** none (verification only)

- [ ] **Step 1: Arch-guard grep (AC1, AC2)**

Run: `grep -rn "resolve_agent_token\|DEPRECATED_TOKEN_ALIASES\|_warned_deprecated" src/`
Expected: **no output**. Any hit is a missed call site — fix before proceeding.

- [ ] **Step 2: Ruff (AC4)**

Run: `uv run ruff check src/agent_toolkit_cli/skill_agents.py src/agent_toolkit_cli/commands/`
Expected: no new errors. Specifically no `F401 unused import sys` (it was deleted) and no unused-import warnings on the trimmed `skill_agents` imports.

- [ ] **Step 3: mypy (AC4)**

Run: `uv run mypy src/agent_toolkit_cli/skill_agents.py 2>&1 | tail -5`
Expected: no NEW errors versus `main` (the repo carries pre-existing mypy debt per prior runs — compare counts, do not require zero).

- [ ] **Step 4: Full suite (AC7)**

Run the changed-surface tests foreground, then the remainder buffered (per the load-average pipe-death trap — never `pytest -q | tail` the whole suite under load):

```bash
uv run pytest tests/test_token_removal.py tests/test_no_legacy_tokens.py \
              tests/test_skill_agents_interop.py -v
uv run pytest -q 2>&1 | tee /tmp/356-suite.log | tail -30
```

Expected: green except the known pre-existing `test_empty_machine_is_empty` HOME-isolation local failure (it reads real npm globals; green on CI). If any *other* test fails, it is in scope — investigate before opening the PR.

- [ ] **Step 5: Final commit if any verification fix was needed** (otherwise skip — Tasks 1–5 already committed each change).

---

## Self-review notes (author, 2026-06-12)

- **Spec coverage (9 ACs):** AC1→Task 2+6.1; AC2→Task 3+6.1; AC3→Task 1; AC4→Task 2.2+6.2/6.3; AC5→Task 4 (delete + guard); AC6→Task 5 (both docs); AC7→Task 3d (src comment) + Task 4 Step 3 (test comment); AC8 (Release-As 4.0.0 + CHANGELOG)→Task 3 Step 5 commit + PR-merge note (release-please generates CHANGELOG from the `BREAKING CHANGE:` footer); AC9 (suite green)→Task 6.4. All nine mapped.
- **RED proof (verified live against `main`, 2026-06-12):** `universal` and `general-agent` map (no raise) via `_resolve_agents` today → genuine pass→raise flips. `general-skill` already raises today because it aliases to the synthetic `standard-skill` and hits the synthetic guard (raises before AND after; reason differs, outcome same). `test_resolver_symbols_are_gone` and `test_old_spelling_emits_no_deprecation_warning` are the unambiguous RED anchors. At least 4 of Task 1's assertions fail pre-removal — documented inline in the test's NOTE and in Step 2's expected output.
- **Edit-not-sed:** all changes are Edit-tool string replacements; no BSD/GNU sed divergence.
- **No placeholders:** every code step shows the exact before/after.

## Execution

L3 (conditional) recommended — mechanical but breaking and spread across five files; the arch-guard grep + full suite catch drift, but each call-site unwrap deserves a divergence-raise rather than free rein.
