# Rename `general`/`universal` → `standard` (full rename incl. internals) — design

**Issue:** #350 · **Tier:** deep (breaking change to a published CLI token, aliased) · **Date:** 2026-06-10

## Problem

Across the CLI and TUI, "general" (and the older "universal") denotes the subset of
harnesses that comply with the adopted common convention for a given asset kind.
The terminology changes to **standard**. Unlike the v3 `universal`→`General` rename
(#304), which was display-label only, this is a **full rename including internals**:
catalog keys, synthetic-name sets, kind-binding values, TUI registry keys, CLI token
names, and docs.

### Premise correction (recorded 2026-06-10)

The intake claim "lockfile values … with a migration for existing locks" is **false**:

- Lock entries store only `source`/`sourceType`/`ref`/`*Path` — **no agent/harness
  tokens** (`skill_lock.py:32-50`; consistent with #230 "lock records none").
- `~/.agent-toolkit/` contains **no** `general*`/`universal*` directories, and no
  harness symlinks point at such paths.

**There is no lock or disk migration.** Migration is out of scope. Deep tier still
holds: `universal` is a documented, user-typed CLI token (`docs/agent-toolkit/cli.md:20`).

## Decisions (approved by AJ, 2026-06-10)

1. **Drop migration** from scope (premise corrected).
2. **Token names:** `universal` → `standard` (skills bundle pseudo-agent);
   `general-skill`/`general-agent`/`general-instructions`/`general-pi-extension` →
   `standard-skill`/`standard-agent`/`standard-instructions`/`standard-pi-extension`.
3. **Deprecation policy:** old spellings alias to new tokens **with a stderr
   warning** for one cycle; aliases removed at the next major (v4.0.0 milestone).
4. **Alias mechanism:** boundary normalization (single choke point), NOT alias
   entries in the AGENTS catalog.

## Design

### Token catalog (SSOT)

`src/agent_toolkit_cli/skill_agents.py:492-516` — rename the three `AGENTS` dict
keys (`universal`→`standard`, `general-skill`→`standard-skill`,
`general-agent`→`standard-agent`). Display names: "General bundle" → "Standard
bundle" (and equivalents). After this change, internals know **only** new tokens.

### Alias layer (boundary normalization)

A module-level table plus one resolver, living beside the catalog:

```python
DEPRECATED_TOKEN_ALIASES: dict[str, str] = {
    "universal": "standard",
    "general-skill": "standard-skill",
    "general-agent": "standard-agent",
    "general-instructions": "standard-instructions",
    "general-pi-extension": "standard-pi-extension",
}

def resolve_agent_token(name: str) -> str: ...
```

- Applied **only where user input enters**: CLI `--agents`/`-a` parsing and any
  command that accepts agent tokens. Internal call paths never pass old tokens.
- On alias hit: warn once per invocation to stderr —
  `"'universal' is deprecated; renamed to 'standard'. The old spelling will be removed in v4."`
  — then proceed with the new token.
- Unknown tokens (neither new nor aliased) raise `UnknownAgentError` exactly as
  today.
- v4 removal = delete the table + resolver call sites. Nothing else carries the
  old names.

### Internal identifiers

| Site | Change |
|---|---|
| `skill_install.py:57` `_SKILL_SYNTHETIC_NAMES` | `{"universal", "general-skill"}` → `{"standard", "standard-skill"}` |
| `agent_install.py:41` `_AGENT_SYNTHETIC_NAMES` | `{"general-agent"}` → `{"standard-agent"}` |
| `_paths_core.py:22-56` `KindBinding.general_harness_name` | field → `standard_harness_name`; values → `standard-*`. Currently consumed nowhere outside `_paths_core.py`; **renamed, not deleted**, because #351's per-kind info panel will consume it. |
| `skill_state.py:34` `INTERACTIVE_AGENTS` | `("universal", …)` → `("standard", …)` |
| `column_info.py:74` registry key + `:49-50` label | key `"universal"` → `"standard"`; title → "Standard bundle"; drop the #304 display-only-rename comment |
| `instruction_grid.py:339` column header | `general ⓘ` → `standard ⓘ` |

### CLI text

`commands/skill/__init__.py:167,204-217` (help text, accepted-values doc, the
"not a usable agent token" error) and any sibling command groups: replace token
spellings; error messages list new tokens only.

### Docs

- `docs/agent-toolkit/cli.md:20,92` — token references → `standard`, plus a
  deprecation sentence.
- `docs/index.md:34` — "Universal agents" concept → "Standard harnesses".
- `docs/agent-toolkit/harness-matrix.md:55,177,278-279` — per-kind "general"
  column language → "standard".
- One canonical deprecation note in each SSOT doc:
  *standard — formerly "general" (v3), earlier "universal" (pre-v3).*
- Historical CHANGELOG entries and committed specs/plans are **not** rewritten.

### Tests

- Rename existing fixture/assertion occurrences (~258 across tests/).
- New: alias resolution unit tests (each old→new pair), warning-emitted test,
  warning-mentions-new-name test, unknown-token-still-errors test, CLI integration
  test (`-a universal` works + warns; `-a standard` works silently).
- Extend the per-kind arch guard (#252 precedent, `tests/test_subagent_matrix.py`)
  to assert no old token spellings remain in `src/` outside
  `DEPRECATED_TOKEN_ALIASES` and the resolver.

### Versioning

Ships as `feat:` **minor** — aliases keep every old invocation working, so this is
not the breaking release. The breaking change is the **alias removal**, queued as a
follow-up issue on the v4.0.0 milestone.

## Out of scope

- TUI/CLI matrix restructure into Standard / Non-standard column groups — #351
  (depends on this rename).
- Consolidating the bundle pseudo-agent with the per-kind projection entries.
- Lock/store migration (none exists to migrate).
- Rewriting historical changelog/spec/plan documents.

## Acceptance criteria

1. No occurrence of `universal`, `general-skill`, `general-agent`,
   `general-instructions`, `general-pi-extension` as live tokens anywhere in
   `src/` except the alias table + resolver (arch-guard enforced).
2. `-a standard` (and `standard-*` where applicable) accepted everywhere
   `-a universal` was; `-a universal` still works and prints the deprecation
   warning to stderr; unknown tokens still raise `UnknownAgentError`.
3. TUI shows "Standard bundle" / `standard ⓘ`; info modal keyed by `standard`.
4. Docs updated per the sweep list, each SSOT doc carrying the deprecation note.
5. Full test suite green; new alias/warning/arch-guard tests in place.
6. A follow-up issue exists for alias removal, tagged v4.0.0.
