# Asset-type-aware lock key for agents & pi-extensions

**Issue:** #409
**Size:** standard
**Date:** 2026-06-14

## Problem

The toolkit writes one lock file per asset type. Each file's top-level key is
supposed to name what it holds:

| File | Top-level key | Correct? |
|---|---|---|
| `skills-lock.json` | `"skills"` | ✓ |
| `instructions-lock.json` | `"instructions"` | ✓ |
| `mcps-lock.json` | `"mcps"` | ✓ |
| `agents-lock.json` | `"skills"` | ✗ — holds agents |
| `pi-extensions-lock.json` | `"skills"` | ✗ — holds pi-extensions |

`agent_lock.py` and `pi_extension_lock.py` are thin facades that re-export
`skill_lock.write_lock` verbatim, and that writer hard-codes the top-level key as
`"skills"` (`skill_lock.py` `write_lock`:
`body = {"version": ..., "skills": sorted_skills}`). The two newer asset types
(`instructions_lock.py`, `mcp_lock.py`) were written with their own
`read_lock`/`write_lock` and so got correct keys; the two older facades inherited
the skill writer's key.

This is **not** data corruption — the toolkit reads its own files back correctly,
because the reader looks for the same hard-coded `"skills"`. But it is confusing
to anyone reading the raw JSON (your *agents* sit inside a block literally
labelled `skills`), and it makes two of the five asset types inconsistent with
the other three.

### Why this is safe to change

The `"skills"` key is load-bearing **only** for `skills-lock.json`, because that
file is the `vercel-labs/skills` / `npx skills` interop format and an external
tool reads it. `agents-lock.json` and `pi-extensions-lock.json` are
toolkit-native — no external reader exists for them — so their `"skills"` key
buys zero interop value and is purely a re-export artifact. Renaming it there is
internal-only.

## Acceptance criteria

1. `agents-lock.json` written by the toolkit has top-level key `"agents"`.
2. `pi-extensions-lock.json` written by the toolkit has top-level key
   `"pi-extensions"`.
3. `skills-lock.json` is **byte-identical** to today — top-level key `"skills"`,
   v1/v3 dual format preserved (the `npx skills` interop regression guard).
4. An existing `agents-lock.json` / `pi-extensions-lock.json` on disk that still
   uses the legacy `"skills"` key still loads correctly (no silent data loss).
   Such a file migrates to the new key on its next write (any mutating verb).
5. `agent import` / `pi-extension import` of a lock file written by an older
   toolkit (legacy `"skills"` key) round-trips: every entry is read, and the
   resulting on-disk file uses the new key.
6. No change to `instructions-lock.json` or `mcps-lock.json`.
7. The in-memory `LockFile.skills` attribute is unchanged (the ~121 call sites
   across ~35 modules stay untouched).
8. No lock `version` bump.

## Approach

Parameterise the top-level JSON key in the shared reader/writer.

### `skill_lock.py`

Add `root_key: str = "skills"` to `read_lock` and `write_lock`.

- `write_lock` emits `{root_key: sorted_skills}` instead of the hard-coded
  `"skills"`.
- `read_lock` resolves entries from `raw.get(root_key)`, falling back to
  `raw.get("skills")` when `root_key != "skills"` and the new key is absent
  (legacy migration read). When `root_key == "skills"` the fallback is a no-op,
  so skills behaviour is byte-identical.
- The default value `"skills"` means every existing `skill_lock` caller is
  unchanged.
- The in-memory `LockFile.skills` attribute name is **unchanged** — only the
  on-disk serialisation key moves. (Renaming the attribute would churn ~121 call
  sites, most of them legitimate skill code, for a cosmetic in-memory gain. Out
  of scope.)

### `agent_lock.py`

Stop re-exporting `read_lock`/`write_lock` verbatim. Define thin wrappers that
bind `root_key="agents"`, and re-export the wrappers under the same names so
every agent caller (`from agent_toolkit_cli.agent_lock import read_lock`) is
untouched. All other names (`LockEntry`, `LockFile`, `add_entry`, …) continue to
re-export verbatim.

### `pi_extension_lock.py`

Same as `agent_lock.py`, binding `root_key="pi-extensions"`.

## Migration

**Read-both, write-new, no version bump.** Existing on-disk files transition
silently on their next write (any `agent`/`pi-extension` `add`/`install`/
`update`/`remove`). No doctor step, no user action. The `version` field cannot
bump because the writer is shared with `skills-lock.json`, which is pinned to
v1/v3 for `npx skills` interop; a bump there would break that contract.

## Error handling / fail-loud

The legacy fallback is read-only and additive. It never hides a malformed file:
a non-dict under either key still yields an empty lock exactly as today
(`read_lock`'s existing `isinstance(..., dict)` guards are unchanged). The
hard-cutover alternative (reader reads only the new key) was **rejected** — it
would silently zero every existing agents/pi-extensions lock on the next read,
violating the fail-loud convention.

## Test surface

TDD target (unit, R0):

- `write_lock(path, lock, root_key="agents")` → file has top-level `"agents"`,
  not `"skills"`.
- `write_lock(..., root_key="pi-extensions")` → top-level `"pi-extensions"`.
- `read_lock(path, root_key="agents")` reads a file whose top-level key is the
  **legacy** `"skills"` (migration proof) — all entries present.
- `read_lock(path, root_key="agents")` reads a file whose top-level key is the
  **new** `"agents"` (round-trip) — all entries present.
- `write_lock` then `read_lock` with default `root_key` → `skills-lock.json`
  output byte-identical to a pre-change golden (interop regression guard), both
  v1 and v3.
- `agent_lock.read_lock`/`write_lock` resolve to `root_key="agents"` without the
  caller passing it; `pi_extension_lock` likewise to `"pi-extensions"`.

End-to-end (R0/R1, exercised through the import command):

- `agent import <legacy-key-file>` reads every entry and the resulting library
  lock is keyed `"agents"`.
- Same for `pi-extension import`.

## Out of scope

- Renaming the in-memory `LockFile.skills` attribute.
- Any change to `skills-lock.json`, `instructions-lock.json`, `mcps-lock.json`.
- A lock `version` bump.
- A proactive doctor migration finding (read-both covers correctness; a file
  only lingers on the legacy key until its next mutating verb, which is
  acceptable).

## Affected files

- `src/agent_toolkit_cli/skill_lock.py` — add `root_key` param to `read_lock`
  and `write_lock`.
- `src/agent_toolkit_cli/agent_lock.py` — wrap to bind `root_key="agents"`.
- `src/agent_toolkit_cli/pi_extension_lock.py` — wrap to bind
  `root_key="pi-extensions"`.
- tests — new unit coverage in the skill_lock test module (or a new
  agent_lock/pi_extension_lock test module) plus import round-trip assertions.
