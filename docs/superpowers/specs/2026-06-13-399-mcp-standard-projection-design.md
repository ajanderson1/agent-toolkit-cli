# MCP `standard` projection — the shared project `.mcp.json` slot

**Issue:** #399 · **Tier:** deep · **Date:** 2026-06-13 · **Scope:** project only

## Summary

Promote the project `<project>/.mcp.json` file (root key `mcpServers`) — today
written independently by the `claude-code` and `pi` MCP adapter cells — to a
first-class **`standard`** projection for the MCP kind. At **project scope**,
`claude-code` and `pi` normalize to `standard`: one canonical entry, one lock
row, one write. This mirrors the agent kind's `standard` slot
(`agent_adapters/standard.py`, #361) and its `claude-code → standard`
normalization (`commands/agent/_common.py:43`).

## Premise correction (load-bearing)

The issue originally claimed root `.mcp.json`/`mcpServers` is read by "the
majority of clients (Claude Code, Cursor, Windsurf, Cline, Continue, Claude
Desktop)." **This is false** (well-sourced; see the issue's premise-check
comment). Only **Claude Code** reads a bare root `.mcp.json`. Cursor uses
`.cursor/mcp.json`, VS Code uses `.vscode/mcp.json` with key `servers`,
Kiro/Continue use subdirs, Windsurf/Cline/Claude-Desktop have no root project
file. **No client reads `~/.mcp.json`** at global scope. The MCP "universal
config" proposal (modelcontextprotocol#2218) is an unratified community
discussion.

What is **real today**: the project `<project>/.mcp.json` is shared by
`claude-code` AND `pi` in our own code (`json_config.py:83,93`). So the honest
value is removing that double-write and naming the shared file — **not** reaching
a broad ecosystem. The design is scoped accordingly.

## Scope

**In scope (project only):**
- A `standard` projection writing `mcpServers.<slug>` into `<project>/.mcp.json`.
- Project-scope normalization `claude-code → standard`, `pi → standard`.
- `STANDARD_MCP_READERS = {"project": frozenset({"claude-code", "pi"})}`,
  documented to grow as #2218 ratifies.
- `list` / `status` / `doctor` understanding of `standard`.
- A non-destructive `doctor` reconciliation of legacy `{claude-code, pi}`
  two-row project locks into one `standard` row.

**Out of scope (explicit):**
- **Global `~/.mcp.json` projection — DROPPED.** Zero native readers → inert.
  Global-scope `claude-code`/`pi` keep their own cells (`~/.claude.json`,
  `~/.pi/agent/mcp.json`) and are **not** normalized.
- Writing any non-Claude-Code/Pi client config (`.cursor/`, `.vscode/`, …).
- Codex (TOML) and OpenCode (`mcp` key) behavior — unchanged.
- The #398 TUI MCP tab (separate issue; this supplies its covered-set data).

## Architecture

### The `standard` adapter — a thin JSON specialization

`standard` reuses the existing `_JsonAdapter` mechanism verbatim. The only
difference from the `claude-code` / `pi` cells is identity, not behavior — at
project scope all three already write `mcpServers.<slug>` into the **same path**
(`<project>/.mcp.json`). We add a `_Cell` for `standard`:

```python
"standard": _Cell(
    name="standard",
    user_target=...,      # global UNSUPPORTED — see below
    project_target=lambda proj: proj / ".mcp.json",
    servers_key="mcpServers",
    translate=_passthrough,
),
```

Because there is **no global standard target**, `standard.config_target(scope="global", …)`
must **raise** (not silently fall back). The cleanest expression: `standard`'s
`user_target` raises `ValueError("standard: no global target — standard is a
project-scope projection")`. This keeps `get_adapter("standard")` usable while
making a global standard write a loud, structured failure that the CLI surfaces.

`get_adapter` dispatches `standard` through the JSON mechanism like any other
JSON-family harness — add `"standard": "json"` to `_MECHANISM`. No special
pre-dispatch branch is needed (unlike the agent kind, whose `standard` adapter is
a genuinely different copy-and-sentinel mechanism; ours is byte-identical to the
existing JSON path, so a plain CELLS entry suffices).

### Project-scope normalization — `normalize_harness_tokens` (MCP-specific)

`commands/mcp/_common.py:11-12` currently documents that
`parse_harness_tokens` is **deliberately NOT ported** ("MCP harnesses … have no
synthetic names"). This change **reverses that decision** and adds a
MCP-specific normalizer, named `normalize_harness_tokens` (NOT
`parse_harness_tokens` — see the shape note below).

> **Why the reversal is the load-bearing risk (deep-review #399).** The original
> "not ported" decision was protecting against a real asymmetry the agent kind
> never faces. The agent `standard` slot (`.claude/agents/`) **converges at both
> scopes**, so `claude-code → standard` is scope-*independent* and the lock
> harness name for that file is *always* `standard`. MCP targets **diverge by
> scope**: claude-code is `~/.claude.json` global but shares `.mcp.json` project;
> pi is `~/.pi/agent/mcp.json` global but shares `.mcp.json` project. So a
> synthetic name can only be honest at ONE scope — hence the **scope-dependent**
> normalization here. The consequence: the same harness (`claude-code`) is
> `standard` at project scope and `claude-code` at global scope, **within one
> lock-entry type, surfaced by verbs (`update`) that span both scopes at once.**
> Every seam that *iterates lock harnesses or maps harness→path* must therefore
> be audited for the scope-conditional name — `list`'s `tracked_by_path`,
> `doctor`'s per-entry loop, and `update`/`remove`'s fan-out. This spec now
> treats "a scope-conditional harness name" as a cross-cutting invariant, not a
> minor rule (see "Seam audit" below).

**Shape difference from the agent kind:** the agent `parse_harness_tokens`
(`commands/agent/_common.py:25-53`) parses a single comma-separated `--harnesses`
string. The MCP `install`/`uninstall` commands instead use a **repeatable
`--harness` flag** (`multiple=True`), so the tokens arrive already split as a
`tuple[str, ...]`. The MCP normalizer therefore operates on that tuple, not a
raw string — name it `normalize_harness_tokens(tokens: tuple[str, ...], *,
scope: str) -> tuple[str, ...]` to avoid implying the comma-split shape. It is
**scope-aware**, the rule the agent kind lacks:

- **At project scope**: `claude-code → standard`, `pi → standard`; dedupe
  preserving order. So `--harness claude-code --harness pi` collapses to a single
  `standard` token / one write / one lock row.
- **At global scope**: NO normalization — `claude-code` and `pi` pass through
  unchanged (they have genuinely separate global files). `standard` is not a
  valid global token (the adapter raises if reached).

The `_common.py:11-12` comment is rewritten to explain the reversal: the project
`.mcp.json` *is* the standard slot, so MCP does normalize — but only at project
scope, because global has no shared standard file.

### Default install set (no `--harness` flag)

Today `_HARNESSES = (claude-code, codex, opencode, pi)` is the no-flag default
(`install_cmd.py:57`). After this change:

- **Project scope default** → `(standard, codex, opencode)`. `standard` covers
  claude-code+pi (one `.mcp.json` write); codex and opencode are the genuine
  outliers. This is the de-dup the issue wants.
- **Global scope default** → unchanged `(claude-code, codex, opencode, pi)` —
  there is no global standard.

This requires the default set to be **scope-aware**. The `--harness`
`click.Choice` (used by `install_cmd.py:33` and `uninstall_cmd.py:35`) must
accept `standard` AND the four concrete harnesses (validation is permissive at
the Choice layer; `normalize`/`apply` enforce the scope rules). Introduce a
helper `default_harnesses(scope) -> tuple[str, ...]` in `_common.py` so the
scope-aware default lives in one place; `install_cmd.py:57`
(`list(harnesses) or list(_HARNESSES)`) calls it instead of the bare
`_HARNESSES` constant.

**All `_HARNESSES` call sites must be audited** (the constant is referenced by
`install_cmd`, `uninstall_cmd`, and `list_cmd` at three iteration sites). The
constant stays as the **concrete-harness universe** (claude-code/codex/opencode/
pi) used for config-scanning loops in `list_cmd` (lines 101/133/148, which read
real per-harness configs and must keep enumerating the concrete four — they do
NOT iterate `standard`, since `standard` has no config file of its own beyond the
`.mcp.json` that claude-code/pi already cover). Only the **default install set**
and the **`--harness` Choice** gain `standard`. The plan must keep these two
roles distinct: `_HARNESSES` = concrete config-scan universe;
`default_harnesses(scope)` = what a no-flag install writes; `--harness` Choice =
concrete four + `standard`.

### Lock — a new value, not a schema change

`McpLockEntry.harness` is already a free string. `standard` is a new **value**;
the versioned envelope `{"version": 1, "mcps": …}` is structurally unchanged. No
*structural* migration. `read_lock`/`write_lock`/`upsert_entry`/`remove_entry`
round-trip arbitrary harness strings.

**Open-set forward-only contract (deep-review data-integrity F1).** The `harness`
field is an open value set: a binary that predates a given value rejects that row
at `get_adapter` dispatch (`UnsupportedMcpHarnessError`). This is acceptable for
the tool's single-user/single-version model, but the contract must be made
explicit — add a line to the `mcp_lock.py` module docstring stating that `harness`
is an open set and the "no migration" freedom is bounded to forward-compatible
*additions*, never silent.

### Collapse-on-install — the migration that actually converges (deep-review C / data-integrity F2–F4)

**The hazard.** `upsert_entry` (`mcp_lock.py:79-84`) dedupes **by harness name
only**. A project that installed before this change has `claude-code` + `pi` lock
rows for the shared `.mcp.json`. Naively upserting a `standard` row leaves those
two rows in place → **three rows for one physical entry**. Worse, `is_installed`
is identity-blind (`json_config.py:148-153`: "does the name exist in the file"),
so a later partial uninstall of *any* of the three deletes the shared entry out
from under the other two → phantom `missing` findings + an orphan `pi` row that
the `standard` workflow can never reach. The originally-planned remediation ("just
re-run `mcp install -p`") was a **no-op** — it only *adds* `standard`, never drops
the legacy rows.

**The fix (single change that heals the whole cluster).** When `apply()` writes a
`standard` projection at project scope, it MUST **drop every lock row whose
harness is in `mcp_standard_covered("project")`** ( `{claude-code, pi}` ) for that
slug, folded into the **same atomic `write_lock`** as the `standard` upsert. So
installing `standard` *collapses* the covered legacy rows rather than coexisting
with them. This makes the doctor remediation honest (re-running `mcp install -p`
genuinely converges to one row), keeps the inconsistent 3-row state transient
(it exists only in-memory between the upsert and the drop, inside one atomic
write), and needs no new atomicity machinery.

Mechanism: a small helper `collapse_covered(lock, slug, covered)` in `mcp_lock.py`
that returns a lock with the covered-harness rows removed for `slug`. `apply()`
calls it right after the `standard` `upsert_entry`, before `write_lock`. Guard it
to project scope + the `standard` harness only (global never produces a standard
row). This is the ONE place `apply()` changes — the rest of the facade
(fan-out, rollback, hand-rolled collision, sentinel gate) is untouched.

### `list` / `status` — expand `standard` to its covered set, and fix the unmanaged-scan

`list_cmd` iterates the concrete `_HARNESSES` to print an installed/absent mark
per harness (`list_cmd.py:101-119`) and separately groups lock-tracked slugs by
**resolved config path** to dedupe the shared `.mcp.json` when surfacing
unmanaged entries (`list_cmd.py:121-159`).

**The unmanaged-scan bug (deep-review A / feasibility F1 / scope F3).** The
path-grouping de-dup builds `tracked_by_path` by iterating `_HARNESSES` and
collecting slugs whose lock rows match those concrete names (`list_cmd.py:133,
141-145`). After normalization, a project-installed slug has a **`standard`** row
and NO claude-code/pi rows — so `tracked_by_path[<project>/.mcp.json]` is **empty**
for it, and the entry is falsely re-surfaced as `[!] unmanaged: <slug>
(claude-code)`. The happy path (`mcp install <slug> -p; mcp list -p`) then prints
BOTH `standard → claude-code, pi` AND `[!] unmanaged: <slug>` — self-contradicting.
This breaks the existing `test_mcp_list_managed_shared_file_not_flagged_unmanaged`.

**The fix.** The `tracked_by_path` grouping must credit a `standard` lock row
toward the `.mcp.json` path. Concretely: in the grouping loop, also resolve the
`standard` adapter's project target (`<project>/.mcp.json`) and union the slugs
with a `standard` row into that path's tracked set. (The per-harness *mark* loop
at `:101-119` stays on `_HARNESSES` — that part is fine; only the
`tracked_by_path` scan needs `standard`.) A regression test must assert
`[!] unmanaged` is **absent** after a standard install.

**Covered-set line (additive).** When a slug has a `standard` lock row (project
scope), print a `standard → claude-code, pi` summary line sourced from
`mcp_standard_covered("project")`.

`status` (`status_cmd.py`) renders each locked slug's harnesses from the lock; a
`standard` harness row gains a `→ claude-code, pi` covered-set annotation, keyed
off the **resolved scope** (not a hardcoded `"project"`), so a stray global
`standard` row degrades loudly rather than silently mis-annotating.

### `list` / `status` — expand `standard` to its covered set

`list_cmd` iterates the concrete `_HARNESSES` to print an installed/absent mark
per harness (`list_cmd.py:101-119`) and separately groups lock-tracked slugs by
**resolved config path** to dedupe the shared `.mcp.json` when surfacing
unmanaged entries (`list_cmd.py:121-159`). Both of those mechanics stay — the
per-harness marks still correctly show claude-code ✔ / pi ✔ against the shared
`.mcp.json`, and the path-grouping de-dup still guards codex/opencode.

What's **added**: when a slug has a `standard` lock row (project scope), print a
`standard → claude-code, pi` summary line sourced from
`mcp_standard_covered("project")`, so the user sees that the `standard` row
covers both. This is additive output, not a rewrite of the per-harness loop —
the loop already handles the concrete harnesses correctly.

`status` (the locked-projection summary, `status_cmd.py`) renders each locked
slug's harnesses from the lock; a `standard` harness row gains the same
`→ claude-code, pi` covered-set annotation.

### `doctor` — legacy-lock reconciliation finding + `standard`-row coverage

**The reconciliation finding.** `doctor` gains a read-only finding
`legacy-standard-dedup` when, at **project scope**, a slug's lock rows include
`claude-code` and/or `pi` **alongside or instead of** `standard` — i.e. the
two-row legacy shape **OR** the partially-collapsed three-row shape (deep-review
data-integrity F4: the check must also fire when `standard` coexists with a
covered row, so an orphan `pi` row left by a non-normalized uninstall is
surfaced, not hidden). The recommended remediation is `mcp install <slug> -p`,
which **now genuinely collapses** (see "Collapse-on-install" above) — the
remediation is honest, not a no-op. Doctor stays read-only (`doctor_cmd.py:1`);
it emits the finding and prints the exact command.

Precise trigger: at project scope, fire `legacy-standard-dedup` for a slug whose
lock-row harness set intersects `{claude-code, pi}` **and** that intersection is
non-empty — covering both `{claude-code, pi}` (pure legacy) and
`{standard, pi}` / `{standard, claude-code, pi}` (partially collapsed). A clean
`{standard}` row does NOT fire it.

**`standard`-row coverage in the EXISTING checks (deep-review B / scope F4).**
Once `standard` is in `CELLS` (Task 2), `doctor`'s existing per-entry loop
(`doctor_cmd.py:130-165`) runs its `missing` / `drifted` / `orphan-library`
checks against `standard` rows too. For a pristine project standard install this
works (passthrough `_rendered_entry` == `_installed_entry`), but it is currently
**untested**, and there is a global-scope edge: `config_target(scope="global")`
for `standard` **raises** `ValueError` (caught at `doctor_cmd.py:137` →
`installed=False` → a misleading `missing`). The design must:
- add a TDD test that `mcp doctor -p` on a clean `standard` install reports
  `all clean` (no `missing`/`drifted`);
- guard the per-entry loop so a `standard` row at **global** scope is skipped (or
  reported as a structured `invalid-standard-row`), never a false `missing`.

## Components & boundaries

| Unit | Responsibility | Depends on |
|---|---|---|
| `mcp_adapters/json_config.py` CELLS `standard` | The project `.mcp.json` target + global-raise | `_JsonAdapter` (unchanged) |
| `mcp_adapters/__init__.py` `_MECHANISM` | `standard → json` dispatch | — |
| `mcp_standard.py` (new) `STANDARD_MCP_READERS`, `mcp_standard_covered(scope)` | Covered-set SSOT (mirrors `agent_adapters/standard.py:25-38`) | — |
| `mcp_lock.py` `collapse_covered(lock, slug, covered)` (new) | Drop covered legacy rows when writing `standard` | — |
| `commands/mcp/_common.py` `normalize_harness_tokens(scope)` + `default_harnesses(scope)` + `_CHOICE_HARNESSES` (all new) | Project normalization, default set, Choice universe | `STANDARD_MCP_READERS` |
| `mcp_install.py` `apply()` | Collapse-on-install (the ONE facade change) | `mcp_lock.collapse_covered` |
| `commands/mcp/install_cmd.py` | Wire scope-aware default + `standard` Choice + normalize | `_common`, `mcp_install` |
| `commands/mcp/uninstall_cmd.py` | `standard` Choice + normalize | `_common`, `mcp_install` |
| `commands/mcp/{list,status}_cmd.py` | `standard` covered-set line + `tracked_by_path` fix | `mcp_standard` |
| `commands/mcp/doctor_cmd.py` | `legacy-standard-dedup` + `standard`-row coverage | `mcp_lock`, `mcp_standard` |

### Seam audit — every site that iterates lock harnesses or maps harness→path

The scope-conditional harness name (above) means these seams must each be
verified against a `standard` row, not just install/uninstall:

- **`apply()`** — the ONE facade change: collapse-on-install (covered above).
  Otherwise `standard` flows through the existing fan-out, rollback,
  hand-rolled-collision, and the sentinel gate (`_sentinel_present`,
  `mcp_install.py:73`, project short-circuits `True`, so `standard` is never
  sentinel-gated).
- **`uninstall()` / `remove()`** — fan over literal lock harnesses
  (`mcp_install.py:224, 256`). For a CLEAN post-#399 lock they just see a
  `standard` row → `get_adapter("standard")` → removes the `.mcp.json` entry.
  Correct. `remove` (full fan-out) self-heals a coexisting legacy lock by
  idempotent repeated deletes. **Add a `remove` regression test** asserting a
  `standard` install fully removes (entry gone, lock row gone).
- **`update`** — `update_cmd.py:174` replays `[e.harness for e in lock...]` per
  scope. For a clean project lock it re-projects the single `standard` row
  correctly (one `.mcp.json` write). **Add an `update` regression test**: a
  post-#399 project lock updates to a single standard write, and the per-scope
  report shows `[project] standard` (vs `[global] claude-code, pi` if a global
  lock exists — the by-design scope divergence, made explicit so it is not a
  surprise). `update` does NOT need to normalize (it replays persisted rows, and
  collapse-on-install already converged them); but the test pins the expectation.
- **`list`** — `tracked_by_path` fix (covered above).
- **`doctor`** — `legacy-standard-dedup` + existing-check coverage (covered above).

## Data flow — `mcp install context7 -p` (no flag)

1. `install_cmd` resolves scope=project, computes default set `(standard, codex, opencode)`.
2. `mcp_install.apply(harnesses=[standard, codex, opencode], scope=project, …)`.
3. For `standard`: `get_adapter("standard")` → JSON adapter with the `.mcp.json`
   project target → upsert `mcpServers.context7` → lock row `harness=standard`.
4. codex/opencode project cells write their own files as today.
5. `.mcp.json` has one managed `mcpServers.context7`; lock has one `standard`
   row for it (not two).

## Error handling

- **Global `standard` write** → `ValueError` from the adapter's `user_target`,
  surfaced as a clean `ClickException` (caught like `UnsupportedMcpHarnessError`
  in `install_cmd.py:67`). A `standard` token at global scope is rejected at
  `parse`-time with a `UsageError` before reaching the adapter.
- **Hand-rolled collision** in `.mcp.json` → existing loud warning
  (`mcp_install.py:147-152`) fires for `standard` unchanged.
- **`--harness standard --harness claude-code -p`** → both normalize to
  `standard`, dedupe to one — no double write, no spurious collision warning.
- **Rollback** → `standard` rides the existing LIFO unwind (`mcp_install.py:163-183`).

## Testing strategy

TDD targets (each RED-first):

1. `standard` adapter writes `mcpServers.<slug>` to `<project>/.mcp.json`;
   preserves sibling entries; idempotent (byte-identical re-write).
2. `standard` adapter `config_target(scope="global")` **raises** (no global target).
3. `normalize_harness_tokens` (project): `claude-code → standard`, `pi → standard`,
   `[claude-code, pi]` dedupe to `[standard]`.
4. `normalize_harness_tokens` (global): `claude-code`/`pi` pass through unchanged;
   `standard` token rejected with `UsageError` — **the load-bearing asymmetry test**.
5. No-flag default install set is scope-aware: project → `(standard, codex,
   opencode)`; global → `(claude-code, codex, opencode, pi)`.
6. `install --harness standard --harness claude-code -p` → one `.mcp.json`
   write, one `standard` lock row.
7. **Collapse-on-install (deep-review C):** a project lock seeded with legacy
   `claude-code` + `pi` rows, then `mcp install <slug> -p` → the lock has EXACTLY
   one `standard` row (claude-code/pi rows DROPPED, not coexisting). Verifies the
   migration actually converges.
8. **`list` no-false-unmanaged (deep-review A):** `mcp install <slug> -p; mcp list
   -p` → output contains `standard → claude-code, pi` and does NOT contain
   `[!] unmanaged: <slug>`. (Pins the `tracked_by_path` fix.)
9. `list`/`status` expand a `standard` lock row to `claude-code, pi`.
10. `doctor` emits `legacy-standard-dedup` for a project lock with the legacy
    `claude-code`+`pi` shape AND for the partially-collapsed `{standard, pi}`
    shape; read-only (lock byte-unchanged); prints the remediation command.
11. **`doctor` clean on a standard install (deep-review B):** `mcp install <slug>
    -p; mcp doctor -p` → `all clean` (no `missing`/`drifted` on the `standard`
    row). Pins the existing-check coverage.
12. **`update` regression:** a clean post-#399 project lock `mcp update <slug>` →
    a single `.mcp.json` write, the `standard` row re-pinned, report shows
    `standard`.
13. `uninstall`/`remove` of `standard` removes only the named `.mcp.json` entry,
    preserves siblings; `remove` fully clears a standard install (entry + row);
    codex/opencode regression guard (unaffected).

**QA playbook (Stage 3):** in a scratch project, `mcp install context7 -p`;
assert `.mcp.json` has `mcpServers.context7` and the lock has one `standard`
row; assert `opencode.json` (if opencode sentinel present) has its own entry and
is untouched by the standard write; `mcp list -p` reports `standard → claude-code,
pi` and NO `[!] unmanaged`; `mcp doctor -p` is `all clean`; hand-seed a legacy
two-row lock and confirm `mcp install context7 -p` collapses it to one `standard`
row; `mcp uninstall context7 --harness standard -p`; assert the entry is gone and
sibling entries (hand-add a dummy `mcpServers.other` first) survive.

## Open decisions — all resolved

| Decision | Resolution |
|---|---|
| Replace vs layer | **Replace** — `standard` owns project `.mcp.json`; claude-code/pi normalize. |
| Global path | **Dropped** — no global standard (zero readers). |
| Coverage model | `STANDARD_MCP_READERS = {project: {claude-code, pi}}`, grows w/ #2218. |
| Lock | New `harness` value; no structural migration; open-set forward-only contract documented. |
| Default set | Scope-aware: project `(standard, codex, opencode)`; global unchanged. |
| Legacy migration | **Collapse-on-install**: `apply()` drops covered legacy rows into the same atomic `write_lock` when writing `standard` — the doctor remediation genuinely converges. |
| doctor reconciliation | Read-only `legacy-standard-dedup` finding (fires on 2-row AND partially-collapsed shapes) + `standard`-row coverage in existing checks. |
| `list` unmanaged-scan | `tracked_by_path` credits `standard` toward `.mcp.json`; no false `[!] unmanaged`. |
| update/remove | Audited + regression-tested (replay persisted rows; collapse already converged them). |
| Ownership | By-name (existing manage-by-name + collision warning); no file sentinels. |
