# Asset-type-aware lock key for agents & pi-extensions

**Issue:** #409
**Size:** standard
**Date:** 2026-06-14
**Critical review:** `ce-doc-review` run 2026-06-14 (coherence, feasibility, adversarial, product-lens, scope-guardian) — findings folded in below; see `## Critical review` on the issue.

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

### Why fix it rather than just document it

The issue was filed because a docs pass surfaced the quirk and asked whether it's
a bug or a quirk-to-document. We fix rather than document because the on-disk lie
is a **recurring comprehension cost**: every future reader (future-AJ, every
agent) who opens `agents-lock.json` hits the mislabelled block, re-derives that
it's "just a re-export artifact," and re-confirms it's safe — a tax paid forever
to avoid a one-time fix. And the fix is a defaulted parameter, not a refactor:
its blast radius is smaller than the documentation debt it retires.

### Why this is safe to change (interop)

The `"skills"` key is load-bearing **only** for `skills-lock.json`, because that
file is the `vercel-labs/skills` / `npx skills` interop format and an external
tool reads it. `agents-lock.json` and `pi-extensions-lock.json` are
toolkit-native — no external reader exists for them — so their `"skills"` key
buys zero interop value. Renaming it there is internal to the toolkit's own
read/write — but **not** free across toolkit *versions* on a synced file; see
§ Migration.

## Acceptance criteria

1. `agents-lock.json` written by the toolkit has top-level key `"agents"`.
2. `pi-extensions-lock.json` written by the toolkit has top-level key
   `"pi-extensions"`.
3. `skills-lock.json` is **byte-identical** to today — top-level key `"skills"`,
   `version` 1 (or 3 where it was 3), v1/v3 dual format preserved (the
   `npx skills` interop regression guard).
4. An existing `agents-lock.json` / `pi-extensions-lock.json` on disk that still
   uses the legacy `"skills"` key at `version` 1 still loads correctly (no
   silent data loss). Such a file migrates to the new key **and** to `version` 2
   on its next write (any mutating verb).
5. `agent import` / `pi-extension import` of a lock file written by an older
   toolkit (legacy `"skills"` key, version 1) reads every entry and writes the
   resulting on-disk file with the new key at version 2. (Round-trip is at the
   *entry-key* level — see the v3-extras caveat in § Out of scope.)
6. No change to `instructions-lock.json` or `mcps-lock.json`.
7. The in-memory `LockFile.skills` attribute is unchanged (the ~121 call sites
   across ~35 modules stay untouched).
8. **`bundle_dispatch._lock_has_member` reads the agent/pi lock with the matching
   asset-type key** — its already-present idempotency precheck returns the right
   answer against a new-key lock file.
9. A new-key agents/pi-extensions file is written at `version` 2; `skills-lock`
   is never written at version 2. An old toolkit reading a version-2 file
   **fails loud-empty** (its version gate rejects it) rather than silently
   rewriting it.

## Approach

Parameterise the top-level JSON key — and the written version — in the shared
reader/writer.

### `skill_lock.py`

1. **`write_lock`** gains `root_key: str = "skills"` and emits
   `{root_key: sorted_skills}` instead of the hard-coded `"skills"`. The
   `"version"` field is still inserted **before** the entries key, so the
   default-`root_key` output is byte-for-byte today's (AC3).
2. **`write_lock`** also honours `lock.version` as today — the facades set the
   version on the `LockFile` they pass (see below), so no new param is needed on
   the writer for the version; the version travels on the struct.
3. **`read_lock`** gains `root_key: str = "skills"`. It resolves entries from
   `raw.get(root_key)`, falling back to `raw.get("skills")` **only when**
   `root_key != "skills"` and the new key is absent (legacy migration read).
   When `root_key == "skills"` the fallback is a no-op, so skills behaviour is
   byte-identical.
4. **`SUPPORTED_VERSIONS`** gains `2` → `(1, 2, 3)`, so a new reader accepts a
   version-2 file. `CURRENT_VERSION` stays `1` (skills' default). The version a
   file is *written* at is carried on the `LockFile.version` the caller hands in,
   never forced by the writer.
5. **Both-keys-present rule:** when a file somehow carries *both* `"agents"` and
   `"skills"` (reachable only in a mixed-version sync accident), `read_lock`
   prefers the `root_key` block and ignores the legacy one. This is
   **read-either-prefer-new, not merge** — stated explicitly because it discards
   the legacy block's data; the version-2 gate (AC9) makes this case unreachable
   in normal operation, but the rule is defined and tested.
6. **Code comment** beside `root_key`: it is the *on-disk* top-level key; the
   in-memory attribute stays `LockFile.skills` because `LockEntry`/`LockFile`
   are the asset-type-blind shared struct reused by agents and pi-extensions by
   design — so a future reader seeing JSON keyed `agents` but `lock.skills` in
   agent code does not mistake it for a bug.

### `agent_lock.py`

Stop re-exporting `read_lock`/`write_lock` verbatim. Define thin wrappers:
`read_lock` binds `root_key="agents"`; `write_lock` binds `root_key="agents"`
**and** stamps `version=2` onto the `LockFile` before writing (so any lock this
facade writes is version 2 with the new key). Re-export the wrappers under the
same names so every agent caller that imports from `agent_lock` is untouched.
All other names (`LockEntry`, `LockFile`, `add_entry`, …) keep re-exporting
verbatim.

### `pi_extension_lock.py`

Same as `agent_lock.py`, binding `root_key="pi-extensions"` and `version=2`.

### `bundle_dispatch.py` (the one facade bypass)

`_lock_has_member` imports `read_lock` **directly from `skill_lock`** (line 192)
and opens `agents-lock.json` / `pi-extensions-lock.json` via the per-asset-type
binding. It bypasses the facades, so the wrappers above do not cover it. Fix:
pass the matching `root_key` per `member.asset_type`
(`"skills"`/`"agents"`/`"pi-extension"` → `"pi-extensions"`) into the
`read_lock` call. (It already has the binding and asset_type in hand; this is a
one-line map.) Every other direct `skill_lock` importer is skill-side and
correctly wants `"skills"` — audited, `bundle_dispatch.py` is the sole bypass.

### Why not `functools.partial` and leave `skill_lock` untouched

A reviewer noted the facades could `functools.partial`-bind the key without
adding a param to `skill_lock`'s public surface. Rejected: the version bump
(AC9) means the facade must also influence the *written version*, which the
serialisation logic owns; threading both through a partial over an unchanged
`skill_lock` is more contortion than a plain defaulted `root_key` param plus a
`version` stamp on the struct. The defaulted param keeps skills callers no-ops
and reads cleanly.

## Migration

**Read-both-keys, write-new-key-at-version-2.** Existing on-disk files
(legacy `"skills"`, version 1) transition on their next write (any
`agent`/`pi-extension` `add`/`install`/`update`/`remove`) to the new key at
version 2. No doctor step, no user action.

**The mixed-version-sync hazard and its defence (review Finding B).** Without a
version bump, an *old* toolkit reading a *new-key* file would find no `"skills"`
key → empty dict → but version 1 passes the old version gate → it returns a
valid-but-empty lock and its next write rebuilds the file from scratch
(`os.replace`), silently dropping the new key (exit 0). On a dotfiles-synced
`~/.agent-toolkit` at mixed toolkit versions this is a steady-state corruption
loop. **Defence: write the new key at `version` 2.** An old toolkit's
`version not in SUPPORTED_VERSIONS` gate then rejects a version-2 file and
returns empty *without* a path that round-trips it back as authoritative — and,
more importantly, the failure is visible (the old toolkit shows zero agents,
prompting the obvious "upgrade the toolkit" rather than silently corrupting).
This is fail-loud per conventions. The version-2 gate also makes the
both-keys-present accident (§ Approach 5) unreachable in normal operation.

Note this is a deliberate, recorded precedent: a toolkit-native lock may migrate
lazily-on-write with a per-asset-type version bump (skills cannot bump — interop
— but agents/pi-extensions, being native, can). Future native-lock changes may
follow this pattern without re-debating it.

## Error handling / fail-loud

The legacy fallback is read-only and additive; it never hides a malformed file
(a non-dict under either key still yields an empty lock via the existing
`isinstance` guards). The version-2 write makes cross-version reads fail visibly
rather than silently. The hard-cutover alternative (reader reads only the new
key, no fallback) was rejected — it would silently zero existing version-1 locks
on the next read.

## Test surface

TDD target (unit, R0), in the skill_lock / agent_lock / pi_extension_lock test
modules:

- `write_lock(path, lock, root_key="agents")` → top-level `"agents"`, not
  `"skills"`; and the file's `version` is whatever `lock.version` carried.
- `agent_lock.write_lock` stamps `version=2` and key `"agents"` without the
  caller passing either; `pi_extension_lock.write_lock` → `version=2`,
  `"pi-extensions"`.
- `read_lock(path, root_key="agents")` reads a **legacy** file
  (`{"version":1,"skills":{…}}`) — all entries present (migration proof).
- `read_lock(path, root_key="agents")` reads a **new** file
  (`{"version":2,"agents":{…}}`) — all entries present (round-trip).
- **Both-keys-present:** `read_lock(root_key="agents")` on a file with *both*
  `"agents"` and `"skills"` returns the `"agents"` block and ignores `"skills"`
  (prefer-new, no merge).
- **Interop regression guard:** `write_lock` then `read_lock` with default
  `root_key` → `skills-lock.json` byte-identical to a **committed pre-change
  golden** (not a dynamically regenerated one), for both v1 and v3. Also assert
  a skills file that happens to contain an `"agents"` key ignores it (fallback
  inert when `root_key=="skills"`).
- **Old-reads-new fail-loud:** a reader with `SUPPORTED_VERSIONS == (1, 3)`
  (simulating the old toolkit) reading a version-2 file returns an empty lock
  (proves the gate rejects it) — guards AC9.
- **Provenance guard (review Finding, low):** an import-provenance or grep check
  that skills command modules import `write_lock` from `skill_lock`, not from
  the facades — the three modules now export identically-named functions with
  different bound behaviour, so an import mixup is a silent correctness bug.

End-to-end (R0/R1, through the import command):

- `agent import <legacy-key v1 file>` reads every entry; resulting library lock
  is keyed `"agents"` at version 2. Same for `pi-extension import`.
- **bundle_dispatch idempotency (AC8):** a bundle install of an already-present
  agent/pi member returns `already_present` against a **new-key version-2** lock
  file (proves `_lock_has_member` reads the right key).

## Out of scope

- Renaming the in-memory `LockFile.skills` attribute (the ~121 call sites). The
  asymmetry "JSON honest, attribute named after the shared struct" is a
  deliberate, stable end state, documented by the § Approach 6 code comment —
  not a half-fix.
- Any change to `skills-lock.json`, `instructions-lock.json`, `mcps-lock.json`.
- A proactive doctor migration finding (read-both covers correctness; a file
  lingers on the legacy key only until its next mutating verb).
- **v3-extras fidelity through import.** `import_cmd` rebuilds a fresh
  `LockEntry` that copies only source/source_type/ref/agent_path/sha and drops
  `entry.extras` (sourceUrl/installedAt/pluginName) — so v3 per-entry extras are
  already lost on import *today*, independent of this change. AC5 is therefore
  scoped to entry-key-level round-trip, not full v3 fidelity. (Agents/pi locks
  are version 1 in practice and never carry v3 wrapper-extras — `dismissed`/
  `lastSelectedAgents` are skills-only and live at the top level, so they are
  `root_key`-agnostic and need no handling here.)
- A lock-format documentation update — the existing `docs/agent-toolkit/lock-files.md`
  ⚠️ note describing the legacy `"skills"` key will need refreshing once this
  ships, but that rides the implementing PR's doc step, not this spec.

## Affected files

- `src/agent_toolkit_cli/skill_lock.py` — `root_key` param on `read_lock`/
  `write_lock`; `SUPPORTED_VERSIONS` → `(1, 2, 3)`; both-keys rule; comment.
- `src/agent_toolkit_cli/agent_lock.py` — wrap to bind `root_key="agents"` +
  `version=2`.
- `src/agent_toolkit_cli/pi_extension_lock.py` — wrap to bind
  `root_key="pi-extensions"` + `version=2`.
- `src/agent_toolkit_cli/bundle_dispatch.py` — `_lock_has_member` passes the
  per-asset-type `root_key`.
- tests — new unit coverage across the lock modules + import round-trip +
  bundle_dispatch idempotency + interop golden.
