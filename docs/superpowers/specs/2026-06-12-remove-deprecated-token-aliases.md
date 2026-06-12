# Spec — remove deprecated `universal`/`general-*` token aliases (#356)

**Issue:** #356 · **Parent:** #350 (introduced the alias layer) · **Tier:** deep
(breaking change to a published interface) · **Date:** 2026-06-12

## Problem

#350 renamed the agent/harness terminology `general`/`universal` → `standard`
and, to soften the break, added a **one-cycle deprecation alias layer**: old
spellings (`universal`, `general-skill`, `general-agent`) still work at the CLI
boundaries but print a stderr warning and map to their `standard` equivalents.
That layer was always scoped as temporary — its own code comment, docstrings,
the `cli.md` terminology note, and the parent AC all say it is **removed in v4**.

#356 performs that removal. After this change the old spellings are no longer
recognised: they fall through to each caller's existing unknown-token guard and
raise `UnknownAgentError` / `click.UsageError` like any other typo.

This is a deliberate hard break. Per AJ's decision (2026-06-12) the **code
removal lands now** as an ordinary change; the **v4.0.0 version bump is deferred**
to a separate later release PR and is explicitly out of scope here. So this PR
carries no `feat!:` / `Release-As:` and cuts no major version.

## What exists today (line-exact, verified 2026-06-12)

The alias machinery is one self-contained block plus five call sites and two
dedicated test files:

**Definition — `src/agent_toolkit_cli/skill_agents.py`**
- L11 `import sys` — **its only consumer is the resolver's `print(..., file=sys.stderr)`** (verified: 1 `sys.` use in the whole file).
- L531–538 comment header + `DEPRECATED_TOKEN_ALIASES` literal (3 entries: `universal→standard`, `general-skill→standard-skill`, `general-agent→standard-agent`).
- L540 `_warned_deprecated: set[str]`.
- L543–560 `def resolve_agent_token(name)` — maps + warn-once.

**Call sites (five)**
1. `commands/skill/_common.py` — import (L10) + `validate_agent_names()` body (L43). *Note: `validate_agent_names` has zero live call sites today (#350 FYI finding); it is dead but still imports the resolver.*
2. `commands/skill/__init__.py` — import (L16), docstring mention (L207–208), `_resolve_agents()` body (L212).
3. `commands/skill/list_cmd.py` — import (L8), `list` body (L54).
4. `commands/agent/_common.py` — deferred import (L36), `parse_harness_tokens()` body (L38), explanatory comment (L19–22 mentions "#350 aliases resolve first").

**Tests**
- `tests/test_token_aliases.py` — entire file is the alias contract (mapping, table shape, warn-once, pass-through, CLI-boundary accept/warn/reject). Deleted wholesale.
- `tests/test_no_legacy_tokens.py` — arch guard that forbids old token spellings in `src/` **except** inside the `DEPRECATED_TOKEN_ALIASES` block (the `_alias_block` allowance, L15–20 + L27). After removal the table is gone, so the allowance is dead and must go; the guard then enforces *zero* old spellings anywhere in `src/`.

**Docs**
- `docs/agent-toolkit/cli.md:22` — terminology note currently reads "*The old token spellings still work for one cycle with a deprecation warning and are removed in v4.*" → must become past tense (removed).

## Design

Pure deletion, no replacement logic. Each call site already has its own
unknown-token rejection downstream of the resolver call, so removing the
`resolve_agent_token(...)` wrapper makes old spellings flow straight into that
rejection:

| Call site | Before | After removal |
|---|---|---|
| `_resolve_agents` | `resolve_agent_token(p)` then unknown-check at L214 | `p.strip()` directly; `universal` is not in `AGENTS` and not `"standard"` → `UsageError` |
| `parse_harness_tokens` | `resolve_agent_token(p)` then unknown-check at L45 | `p.strip()` directly; old spelling not in `AGENTS` → `UsageError` |
| `list_cmd` | `agent = resolve_agent_token(agent)` then unknown-check at L55 | drop the line; `agent` checked directly → `UsageError` |
| `validate_agent_names` (dead) | `resolve_agent_token(n)` then unknown-check | `n` checked directly |

`get_standard_agents` / `is_standard` / `show_in_standard_list` and all other
`standard`-spelled identifiers are **unaffected** — they are the *new* names, not
aliases. Only the three old→new mappings and their machinery are deleted.

`import sys` is removed from `skill_agents.py` (no other consumer) to keep ruff
green. The `#350 aliases resolve first` comment in `agent/_common.py` (L19–22)
is reworded to drop the alias claim while keeping the synthetic-rejection
rationale.

## Behaviour after the change (the break, made concrete)

```
$ agent-toolkit-cli skill install foo --agents universal
Error: unknown agent(s): universal           # was: warning + mapped to standard

$ agent-toolkit-cli agent install bar --harnesses general-agent
Error: unknown harness(es): general-agent     # was: warning + mapped to standard-agent

$ agent-toolkit-cli skill list --agent universal
Error: unknown agent: universal               # was: warning + mapped to standard
```

`standard`, `standard-skill` (still rejected as synthetic), `claude-code`, and
all real harness tokens behave exactly as before.

## Acceptance criteria

1. `DEPRECATED_TOKEN_ALIASES`, `_warned_deprecated`, and `resolve_agent_token`
   are gone from `src/`; `grep -rn "resolve_agent_token\|DEPRECATED_TOKEN_ALIASES\|_warned_deprecated" src/` returns nothing.
2. All five call sites pass the raw token straight to their existing unknown-token
   guard; no resolver import remains anywhere in `src/`.
3. Old spellings raise: `skill install --agents universal`, `agent install
   --harnesses general-agent`, and `skill list --agent universal` each exit
   non-zero with an unknown-token error (no deprecation warning, no mapping).
4. `import sys` removed from `skill_agents.py` (it had no other use); ruff/mypy
   report no new errors versus `main`.
5. `tests/test_token_aliases.py` deleted; `tests/test_no_legacy_tokens.py`
   updated to drop the `DEPRECATED_TOKEN_ALIASES` allowance so it enforces zero
   old spellings in `src/` (and that guard passes).
6. `docs/agent-toolkit/cli.md:22` terminology note updated to past tense ("removed
   in v4" → reflects the alias no longer exists). The "*formerly general /
   universal*" lineage sentence stays.
7. Full suite green except the known pre-existing `test_empty_machine_is_empty`
   HOME-isolation local failure (green on CI).

## Out of scope

- The v4.0.0 version bump / `Release-As` / CHANGELOG breaking-changes entry —
  deferred to a separate release PR (AJ decision 2026-06-12).
- Removing the dead `validate_agent_names` helper itself (only its alias
  dependency is touched; deleting the function is a separate cleanup).
- The "*formerly general (v3), earlier universal (pre-v3)*" historical lineage
  note — kept; only the "still work / removed in v4" clause changes.
- Any rename of `standard`-spelled identifiers (those are the live names).
- Rewriting historical specs/plans/CHANGELOG that mention the old tokens.

## Links

- #350 — introduced the alias layer (parent); its AC6 = "follow-up issue filed
  for v4.0.0 alias removal" — this is that issue.
- `test_no_legacy_tokens.py` arch-guard precedent (#350 / #252).
