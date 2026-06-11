# agent install -p writes a project lock entry (#362)

**Issue:** [#362](https://github.com/ajanderson1/agent-toolkit-cli/issues/362)
**Date:** 2026-06-11
**Tier:** standard

## Problem

`agent install <slug> -p` projects files into the project's harness dirs and
prints `installed <slug> [project]`, but never writes
`<project>/agents-lock.json`. Every project-scope read surface is blind to the
install:

- `agent list -p` → `no agents found`
- TUI agents tab at project scope → empty rows
- project-scope `agent doctor` → no targets; since #366 merged, the orphan
  sweep **actively misclassifies** the tool's own successful install as an
  orphan and offers an `rm` fix.
- re-running the same install conflicts on the tool's own files (PM-review F3
  on PR #366): `apply()` derives `overwrite` from the scope lock entry, which
  never exists at project scope, so `overwrite=False` → `_guard_foreign`
  raises on a file the tool itself projected.

**Root cause (verified on main, 2026-06-11):** `commands/agent/install_cmd.py`
(~l.134) and the TUI (`agent_toolkit_tui/app.py` `_apply_agent_pending`,
~l.909) both build `InstallPlan(source=None, ref=None)`;
`agent_install.apply()` gates its lock write on `plan.source is not None`
(~l.323). No code path writes a project agents lock. Global scope only looks
correct because `agent add` wrote the global entry earlier.

**Why CI stayed green:** the existing project round-trip test
(`tests/test_cli/test_agent_install_roundtrip.py` `…_project_…`) passes
`source=src` into the plan — the source-present lock path — and never
exercises the real CLI/TUI shape (`source=None`). This is the #283/#268 class:
install machinery shipping a silently-broken path with green CI.

## Contract (decided with PM, 2026-06-11)

`agent install -p` (CLI and TUI alike) must leave the project in the same
state the skills kind guarantees: projections on disk **and** a project lock
entry, so list/TUI/doctor/uninstall/remove round-trip.

### 1. Fix point: inside `agent_install.apply()`

Both surfaces call `apply()`, so the fix lives there — not in per-call-site
helpers. Two additions, both gated on
`plan.scope == "project" and plan.source is None and plan.add_agents`:

**(a) Pre-validation — before any mutation.** Read the **global** lock
(`library_lock_path()`). If the slug has no global entry, raise
`InstallError(f"{slug}: no global lock entry; run `agent add {slug}` first")`
*before* the projection loops, so a failed install leaves no orphaned files.

**(b) Lock write — after the projection loops succeed.** If the project lock
has no entry for the slug, derive one from the global entry and write it
(existing v1 writer, atomic). `lock_action` reports `"added"`.

Pure-remove plans (`add_agents` empty) are exempt from both: uninstalling a
slug whose library entry was dropped must keep working.

### 2. Entry shape — mirror of the skills precedent

Exactly `skill_install.ensure_project_canonical`'s derivation
(`skill_install.py:449-458`), agent-flavoured:

| field | value |
|---|---|
| `source` / `source_type` / `ref` | copied from the global entry |
| `agent_path` | global entry's `agent_path`, fallback `f"{slug}.md"` |
| `parent_url` / `read_only` | copied from the global entry |
| `upstream_sha` / `local_sha` | `None` (project entries don't pin SHAs) |

No schema change: the v1 lock format already serialises every field;
`<project>/agents-lock.json` is already the path every project-scope reader
consults (`agent_paths.lock_file_path`).

### 3. Ordering preserves the foreign-file guard

The write happens **after** projection: on a first install
`existing_entry is None` → `overwrite=False` → `_guard_foreign` still refuses
to clobber a pre-existing foreign file. From the second run on the entry
exists → `overwrite=True` → re-install is a permitted refresh of the tool's
own files. This fixes the F3 re-install conflict for post-fix installs as a
side effect, without weakening the guard.

### 4. Fail-loud on the manually-seeded edge (decided with PM)

`install_cmd` today accepts a slug whose global **canonical dir** exists with
no global **lock entry** ("a manually-seeded canonical also counts"). At
project scope there is then nothing to derive the entry from. Decision:
**fail loud** (pre-validation (a)), aligning with the skills kind
(`ensure_project_canonical` raises "not in global library") and the fail-loud
convention. Remediation is in the message: `agent add <slug>`. Global-scope
installs of canonical-only slugs are unaffected (no derivation needed there).
Rejected alternatives: skip-and-warn (the #362 blindness persists);
synthesize `source_type="local"` pointing at the library dir (poisons
update/doctor flows that treat `source` as clonable).

### 5. Migration (documented, not coded)

Pre-fix project installs stay lock-less; doctor continues to flag them as
orphans. Remediation: `agent uninstall <slug> -p` (adapter-direct,
lock-independent) then re-run `agent install <slug> -p`. Automatic adoption
of sentinel-less pre-fix projections belongs to the existing per-adapter
sentinel-adoption follow-up (filed from the #366 review), not this issue.

## Acceptance criteria

1. `agent install <slug> -p` writes a project lock entry at
   `<project>/agents-lock.json` with the §2 shape, after successful
   projection.
2. `agent list -p` lists the agent (✔, non-zero harness count) immediately
   after a project install.
3. The TUI agents-tab Apply at project scope produces the same entry (no TUI
   code change required — verified by a test driving the TUI's plan shape
   through `apply()`).
4. Project-scope `agent doctor` no longer reports the standard slot of a
   just-installed agent as an orphan.
5. Re-running `agent install <slug> -p` succeeds (refresh, not conflict).
6. A fresh project install onto a pre-existing foreign destination file still
   refuses (guard regression test — `overwrite` stays `False` on first
   install).
7. Project install of a slug with no global lock entry fails loud, before any
   file is projected.
8. Round-trip at **both** scopes (the #283/#268 mandate), driven through the
   real `source=None` plan shape:
   install → list shows it → uninstall (projections gone, canonical + lock
   entry KEPT, #303) → remove (lock entry dropped).
9. Global-scope behaviour unchanged: `agent install -g` writes no new global
   lock entries (that remains `agent add`'s job).

## Out of scope

- Global-scope adopt semantics for canonical-only slugs (`agent install -g`
  writing a global entry).
- Per-adapter sentinel adoption for pre-fix sentinel-less projections
  (existing follow-up from the #366 review).
- A doctor "adopt" fix-action for pre-fix lock-less project installs.
- `result.removed` never being populated by `apply()` (known, documented gap).

## Test surface

`tests/test_cli/test_agent_install_roundtrip.py` (extend with `source=None`
round-trips at both scopes), `tests/test_cli/test_agent_install.py` /
`test_agent_install_e2e.py` (CLI-level list-after-install, fail-loud edge,
re-install), `tests/test_cli/test_agent_doctor.py` (no-orphan-after-install),
`tests/test_tui/test_agent_grid.py` or `test_agent_state.py` (TUI plan shape
writes the entry).
