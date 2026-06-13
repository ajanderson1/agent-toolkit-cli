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

### Project-scope normalization — `parse_harness_tokens` for MCP

`commands/mcp/_common.py:11-12` currently documents that
`parse_harness_tokens` is **deliberately NOT ported** ("MCP harnesses … have no
synthetic names"). This change **reverses that decision** and adds a
MCP-specific normalizer.

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
migration. `read_lock`/`write_lock`/`upsert_entry`/`remove_entry` need no
changes — they already round-trip arbitrary harness strings.

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

### `doctor` — legacy-lock reconciliation finding

A project lock written before this change carries **two rows** for the shared
file: `claude-code` and `pi`, both projecting `<project>/.mcp.json`. `doctor`
gains a read-only finding `legacy-standard-dedup` when it sees both
`claude-code` and `pi` rows for the same slug at **project scope**, recommending
collapse to a single `standard` row. The **fix is non-destructive**: the
`.mcp.json` content is already correct (the entry is byte-identical); only the
lock rows collapse. Following the existing MCP-doctor pattern, doctor itself
stays read-only (`doctor_cmd.py:1`) and emits the finding; the actual collapse is
applied by the user re-running `mcp install <slug> -p` (which now resolves to
`standard` and upserts one row) — OR, if a one-shot is wanted, doctor prints the
exact command. (Decision: keep doctor read-only; reconciliation is a printed
remediation, not an in-doctor write — consistent with the existing three doctor
checks.)

## Components & boundaries

| Unit | Responsibility | Depends on |
|---|---|---|
| `mcp_adapters/json_config.py` CELLS `standard` | The project `.mcp.json` target + global-raise | `_JsonAdapter` (unchanged) |
| `mcp_adapters/__init__.py` `_MECHANISM` | `standard → json` dispatch | — |
| `mcp_standard.py` (new) `STANDARD_MCP_READERS`, `mcp_standard_covered(scope)` | Covered-set SSOT (mirrors `agent_adapters/standard.py:25-38`) | — |
| `commands/mcp/_common.py` `parse_harness_tokens` + scope-aware default | Project normalization, default set | `STANDARD_MCP_READERS` |
| `commands/mcp/install_cmd.py` | Wire scope-aware default + `standard` Choice | `_common`, `mcp_install` |
| `commands/mcp/{list,status}_cmd.py` | Expand `standard` to covered set | `mcp_standard` |
| `commands/mcp/doctor_cmd.py` | `legacy-standard-dedup` finding | `mcp_lock` |

`mcp_install.apply()` / `uninstall()` / `remove()` need **no change** —
`standard` is just another harness string flowing through the existing fan-out,
rollback, and hand-rolled-collision machinery. The sentinel gate
(`_sentinel_present`, `mcp_install.py:73`) already short-circuits `True` at
project scope, so `standard` (project-only) is never sentinel-gated — no new
branch needed.

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
3. `parse_harness_tokens` (project): `claude-code → standard`, `pi → standard`,
   `[claude-code, pi]` dedupe to `[standard]`.
4. `parse_harness_tokens` (global): `claude-code`/`pi` pass through unchanged;
   `standard` token rejected with `UsageError` — **the load-bearing asymmetry test**.
5. No-flag default install set is scope-aware: project → `(standard, codex,
   opencode)`; global → `(claude-code, codex, opencode, pi)`.
6. `install --harness standard --harness claude-code -p` → one `.mcp.json`
   write, one `standard` lock row.
7. `list`/`status` expand a `standard` lock row to `claude-code, pi`.
8. `doctor` emits `legacy-standard-dedup` for a project lock with both
   `claude-code` + `pi` rows for one slug; the finding is read-only and prints
   the remediation command; `.mcp.json` is not modified by doctor.
9. `uninstall`/`remove` of `standard` removes only the named `.mcp.json` entry,
   preserves siblings; codex/opencode regression guard (unaffected).

**QA playbook (Stage 3):** in a scratch project, `mcp install context7 -p`;
assert `.mcp.json` has `mcpServers.context7` and the lock has one `standard`
row; assert `opencode.json` (if opencode sentinel present) has its own entry and
is untouched by the standard write; `mcp list -p` reports `standard → claude-code,
pi`; `mcp uninstall context7 --harness standard -p`; assert the entry is gone and
sibling entries (hand-add a dummy `mcpServers.other` first) survive.

## Open decisions — all resolved

| Decision | Resolution |
|---|---|
| Replace vs layer | **Replace** — `standard` owns project `.mcp.json`; claude-code/pi normalize. |
| Global path | **Dropped** — no global standard (zero readers). |
| Coverage model | `STANDARD_MCP_READERS = {project: {claude-code, pi}}`, grows w/ #2218. |
| Lock | New `harness` value; no schema migration. |
| Default set | Scope-aware: project `(standard, codex, opencode)`; global unchanged. |
| doctor reconciliation | Read-only `legacy-standard-dedup` finding + printed remediation. |
| Ownership | By-name (existing manage-by-name + collision warning); no file sentinels. |
