# Spec: Commands standard projection

Issue: #482

## Problem

Commands currently project the same `COMMAND.md` independently to Claude Code,
Pi, and Gemini CLI. The shared `.claude/commands/<slug>.md` location is already
consumed natively by more than one harness, but has no first-class adapter,
ownership record, CLI token, or TUI column.

Research now establishes the actual reader sets:

| Scope | Native readers of the shared slot |
|---|---|
| global | Claude Code, Neovate |
| project | Claude Code, Neovate, Devin CLI (imports commands as skills) |

Evidence is committed at
[`docs/agent-toolkit/research/2026-07-28-command-standard-readers.md`](../../agent-toolkit/research/2026-07-28-command-standard-readers.md).

The currently released Commands grid correctly has **no** Standard column; the
older issue text that described live dead branches was superseded by #485. This
issue adds the projection rather than reverting that cleanup.

## Goal

One toolkit-owned artifact at `.claude/commands/<slug>.md` serves every proven
reader at the chosen scope, is represented as `standard` everywhere, and is the
first `Standard (N)` column in the Commands TUI. Pi and Gemini CLI retain their
separate native projections; deprecated global-only Codex remains explicit and
CLI-only.

## Decisions

### D1 — Dedicated standard adapter, not an alias

Use `command_adapters/standard.py` with its own ownership rules. Reusing the
Claude adapter anonymously would lose the `standard` token, allow duplicate
reporting, and make a Claude-only uninstall able to remove a file Neovate and
Devin consume.

### D2 — The reader SSOT is scope-specific and fail-loud

```python
STANDARD_COMMAND_READERS: dict[str, frozenset[str]] = {
    "global": frozenset({"claude-code", "neovate"}),
    "project": frozenset({"claude-code", "neovate", "devin"}),
}


def commands_standard_covered(scope: str) -> frozenset[str]:
    return STANDARD_COMMAND_READERS[scope]
```

The accessor must raise `KeyError` for an unknown scope. It is the sole source
for CLI defaults, scan normalisation, TUI composition, Standard counts, and
info-panel reader lists. The reader map is broader than the individual adapter
registry on purpose: Neovate and Devin consume the shared artifact without a
separate per-harness projection.

### D3 — Slot and ownership contract

The standard destination is deliberately byte-identical to the Claude Code
Markdown destination:

- global: `~/.claude/commands/<slug>.md`
- project: `<project>/.claude/commands/<slug>.md`

The adapter verifies that canonical `COMMAND.md` is a regular file before any
comparison or mutation. It uses the existing `.attk` sidecar format with
`harness: "standard"` and supports symlink-first projection with the existing
copy fallback. Neither path transforms the Markdown or frontmatter:
Claude-specific fields remain byte-for-byte present so Neovate can ignore
unsupported fields while Claude retains their behavior.

A standard install must:

1. create a symlink to the canonical command when the slot is absent (or a
   regular managed copy when symlinks are unavailable);
2. adopt a pre-standard Claude symlink that resolves to the canonical command,
   or a byte-identical regular file, by writing the Standard sidecar without
   changing its content;
3. refresh a sidecar-owned copy safely; if a stale sidecar accompanies a
   replaced symlink, unlink the slot before recreating it so writes never flow
   through a user symlink;
4. refuse a divergent regular file or foreign symlink without changing it.

Uninstall removes only a sidecar-owned slot, a canonical-resolving legacy
symlink, or a sentinel-less byte-identical legacy file. It leaves a divergent,
unsentinelled file in place and reports the refusal. A missing slot cleans only
its dangling sidecar. These rules make a shared path safe to adopt and safe to
leave behind. `command_install.apply()` validates the source before all writes
and executes the potentially adopting Standard action last; an earlier
Pi/Gemini failure therefore cannot leave a newly claimed shared slot behind.
Rollback never unlinks a destination that predated the operation. If a later
operation fails after Standard adopted an existing legacy path, rollback removes
only the sidecar newly written by that adoption and leaves the legacy file or
symlink intact.

A path is not considered an installed Standard projection merely because it
exists or is adoptable. The Standard scanner returns installed only for a valid
`harness: "standard"` sidecar whose live destination still resolves to the
canonical file (or whose regular-file bytes still match it). A legacy Claude
symlink, matching unsentinelled copy, stale sidecar, or foreign file is an
untracked physical observation; a requested install must reach the adapter so
it can adopt or fail loud instead of silently declaring success.

### D4 — One destination has one token

`standard` is a real, installable Commands token; `standard-command` remains a
rejected synthetic name. `claude-code` normalizes to `standard` because both
names resolve to the same destination. The scanner probes Standard first and
reserves its destination before testing ownership, then skips any later adapter
whose resolved destination is already seen. It records that slot only as
`standard` when the Standard ownership test passes. This prevents an unowned
legacy/foreign `.claude/commands` file from being misclassified as an installed
`claude-code` projection and bypassing the conflict/adoption guard.

The parser accepts `standard` plus the existing concrete command harnesses.
It preserves order while deduplicating aliases. Neovate and Devin are not
separate CLI target names: selecting `standard` serves them automatically.

### D5 — Default and explicit fan-out

Default install is scope-aware and starts with the shared slot:

```text
standard, pi, gemini-cli
```

`codex` remains explicit: its deprecated prompts are global-only and do not
read the standard slot. No default command install makes a duplicate Claude
copy. No-flag uninstall is intentionally maximal — Standard plus all concrete
command targets — so it cleans legacy installations as well as current ones.

### D6 — Projection state is additive and backward-compatible

Commands need a per-scope record of the projections they own. Add a typed,
optional `harnesses` list to `command_lock.LockEntry`; emit it only when
non-empty. The on-disk v1 envelope stays v1:

```json
{
  "version": 1,
  "skills": {
    "demo": {
      "source": "owner/repo",
      "sourceType": "github",
      "commandPath": "COMMAND.md",
      "harnesses": ["standard", "pi", "gemini-cli"]
    }
  }
}
```

Read-time absence means an old lock, not an error. Invalid non-string/list
values fail loud. The field is appended after the existing `extras` dataclass
argument so callers using the old positional constructor remain valid. This is
an expand → backfill → switch → contract rollout:

1. **Expand:** add the optional typed field while preserving old fields and
   unknown extras.
2. **Backfill on mutation only:** install/uninstall scans the real destinations
   for its slug, replaces a legacy `claude-code` record with `standard`, and
   writes deterministic unique tokens only after every requested projection
   succeeds. Reading/listing alone never churns a lock.
3. **Switch:** status, list, doctor, CLI operations, and the TUI use the
   normalized field plus physical probes; the filesystem remains the source of
   truth for drift.
4. **Contract:** a successful standard install never leaves both `standard` and
   `claude-code` in one scope entry. Uninstall removes a token only after its
   owned destination is gone; a refusal leaves its record intact.

A command is `library` when its source entry has no tracked projection in the
active scope, `installed` when a tracked projection exists, and `unlisted` when
only the scope lock knows it. TUI state therefore uses `harnesses` rather than
mistaking every global library entry for an installation.

A first project install derives its source/ref/commandPath entry from the
existing global library lock after projection succeeds, matching the agent
project-lock contract. It never writes an entry for an all-failed installation.
If that first attempt created a project canonical and a projection then fails,
it removes only that newly created canonical as part of rollback; it preserves
an existing canonical and every foreign projection. A manually seeded global
canonical with no library lock preserves today's unlisted behavior: it may
project, but the toolkit does not invent source metadata; doctor reports its
physical projection as untracked. The same rule applies to a first project
projection sourced from that manual global canonical: it may materialise and
project, but creates no project source entry. `command import` imports source
metadata, not another machine's projection state: it explicitly starts imported
library entries with an empty `harnesses` tuple.

### D7 — CLI and doctor semantics

`command install`, `uninstall`, `remove`, `list`, `status`, and `doctor` all
recognize `standard` at both scopes.

- `command_install.apply()` owns one project-canonical materialisation helper;
  CLI install and TUI Apply both enter through that facade, so neither can copy
  a global canonical under different validation, rollback, or lock rules.
- `uninstall` is non-destructive to canonical command content and source
  metadata. `remove` first detaches all recorded/default projections, then
  removes its canonical and lock entry, so it cannot orphan a Standard slot.
- `list --json` exposes normalized `harnesses`; text output shows the same
  comma-separated state. Existing consumers that ignore the added JSON key
  remain valid.
- `status` reports `standard` once when that one slot exists, never both
  `standard` and `claude-code`.
- `doctor` stays read-only. Its slug inventory is the union of active-lock
  entries and direct canonical directories containing a regular `COMMAND.md`,
  so manual canonical installs can be diagnosed without fabricated metadata.
  It reports missing tracked Standard slots, untracked Standard slots, and
  normalised linked targets without attempting adoption or lock backfill.

### D8 — TUI composition and mutation

Commands follow the same scope-aware composition shape as MCPs:

```python
("standard", *commands_nonstandard_main(scope, selection))
```

The Standard column is always first and is not removed by a main-harness
selection. At either scope, Claude Code is covered and therefore does not have
a second Commands column. Pi and Gemini remain individual columns. The header
is `Standard (2)` globally and `Standard (3)` in project scope.

`CommandGrid.set_scope()` rebuilds columns, `command_state` probes the Standard
adapter and derives `library`/`installed` state from the active-scope
`harnesses` record, and `TUIApp._apply_command_pending()` must exist and route
Standard link/unlink operations through the same facade used by the CLI. The current
app has no command-pending apply method; adding an actionable Standard cell
without this would crash after a toggle.

Settings labels explain that Claude's Commands column is Standard-covered;
Neovate and Devin are not added to `MAIN_HARNESSES` merely to make this feature
work.

### D9 — Information copy

Add a `("command", "standard")` column-info factory whose reader list is
resolved from `commands_standard_covered(active_scope)` at panel-open time.
Its sentence must make the semantic difference clear:

- global: one Markdown command slot serves Claude Code and Neovate;
- project: the same slot serves Claude Code and Neovate, while Devin imports
  it as a skill.

Remove the rendered `("command", "claude-code")` info pair because Claude has
no standalone Commands column after the fold. `standard_column_header()` gains
the Commands resolver and the #478 no-standard exception entries disappear.

### D10 — Documentation

Update the command asset page and CLI reference with:

- the standard paths and verified reader sets;
- `standard` and `claude-code` normalization;
- default fan-out and maximal-uninstall asymmetry;
- the optional lock `harnesses` field and non-churning backfill;
- the fact that Devin imports project commands as skills; and
- Codex's unchanged explicit/global-only status.

## Acceptance requirements

1. `STANDARD_COMMAND_READERS` exactly matches D2, and unknown scope fails
   loud.
2. Standard install/uninstall/adoption/refusal/refresh and rollback have
   focused tests at global and project scope.
3. One physical `.claude/commands/<slug>.md` destination is scanned, displayed,
   and recorded only as `standard`.
4. Default install produces Standard + Pi + Gemini, with no duplicate Claude
   write; explicit `claude-code` produces Standard.
5. Existing v1 command locks without `harnesses` remain readable; mutation
   writes a deterministic normalized list without a version bump.
6. Project installs receive a derived project entry only after a successful
   projection; foreign-file failures leave neither a new slot nor a lock lie.
7. CLI list/status/doctor and TUI state show Standard accurately, and doctor
   does not write.
8. Commands TUI renders Standard first with scope-correct counts, no duplicate
   Claude column, working header info, working toggle Apply, and selection
   invariants.
9. Focused CLI/TUI suites and the full pytest suite pass; verification evidence
   is recorded under `assets/verification/issue-482/` during implementation.

## Out of scope

- Adding individual Command adapters for Neovate or Devin.
- Treating unmerged OpenCode or contradicted Kode compatibility claims as
  standard readers.
- Changing `MAIN_HARNESSES`, adding Codex to default/TUI Commands columns, or
  reviving deprecated Codex prompts.
- Replacing command Markdown with skills, changing command source format, or
  modifying Pi/Gemini translation behavior.
- Broad cleanup unrelated to Commands, including the already-resolved #485
  grid docstring work.
