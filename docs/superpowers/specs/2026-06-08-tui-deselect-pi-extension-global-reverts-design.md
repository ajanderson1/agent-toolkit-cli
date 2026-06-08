# Fix #333 — global pi-extension deselect actually removes it

**Issue:** [#333](https://github.com/ajanderson1/agent-toolkit-cli/issues/333) — `fix(tui): deselecting a pi extension at global scope reverts and doesn't remove it`
**Type:** fix
**Date:** 2026-06-08

## Problem

In the TUI, unchecking a pi extension at global scope and pressing Apply (`ctrl+s`)
has no effect: the row reverts to its previous "installed" status after the
post-apply refresh, and the extension is in fact NOT removed from global scope.
The TUI reports `applied: N ok` while leaving global state unchanged.

## Root cause (confirmed in code)

The TUI's `_apply_pi_pending` (`src/agent_toolkit_tui/app.py:783-840`) and the CLI
verbs `uninstall_cmd` / `install_cmd`
(`src/agent_toolkit_cli/commands/pi_extension/`) are **near-duplicate twins** that
each hand-roll the same projection + lock logic. There are two real defects and
one apparent-but-not defect:

1. **npm (real defect).** Removal calls
   `_pi_settings.remove_package(entry.source)`, which deletes a `packages[]` entry
   only on a byte-for-byte match of the lock's stored `entry.source`
   (`src/agent_toolkit_cli/_pi_settings.py:136` — `if spec not in packages: return`).
   On the happy install→uninstall round-trip the stored source equals the written
   `packages[]` string, so it works. It silently no-ops on **drift**: a hand-added
   entry without the `npm:` prefix, a version-pinned `npm:foo@1.2.3` vs a stored
   `npm:foo`, or any normalization difference. The package survives, and
   `build_inventory` reads it back as `global_loaded = True`, so the row reverts.

2. **store-owned global lock (NOT a defect — keep as-is).** The
   `if scope == "project"` guard on the post-apply lock prune (`app.py:817`,
   mirrored in `uninstall_cmd.py:46`) is **correct by design**:
   - The inventory derives `global_loaded` from the on-disk symlink
     (`~/.pi/agent/extensions/<slug>`), **not** the lock
     (`src/agent_toolkit_cli/pi_extension_inventory.py` pass 2). Removing the
     symlink alone makes the row stay unchecked.
   - At global scope the "scope lock" *is* the global library lock
     (`lock_file_path(scope="global")` → `library_lock_path()`). Pruning it on
     `uninstall` would conflate **uninstall** (turn projection off, keep the
     library copy) with **remove** (delete the library copy) — breaking the
     deliberate two-verb contract established in PR #306. So `uninstall -g` for a
     store-owned extension must drop ONLY the symlink and leave the lock entry.

3. **divergence (real defect).** Because the TUI and CLI each reimplement this
   logic, they can drift — and they drift *identically broken* today. The fix must
   collapse them onto one shared path so they cannot diverge again.

## Approach

Extract a pure core, fix it once, delegate both surfaces to it.

## Architecture

### New module: `src/agent_toolkit_cli/pi_extension_ops.py`

Single source of truth for toggling a projection on/off, sitting alongside
`pi_extension_install.py` (which stays the low-level store-owned symlink
projector). Public surface:

```python
def install(*, slug: str, scope: Scope, home: Path | None, project: Path | None) -> None
def uninstall(*, slug: str, scope: Scope, home: Path | None, project: Path | None) -> None
```

- Lifts the exact body of today's `install_cmd` / `uninstall_cmd`: read the global
  library lock → branch on `entry.source_type` → npm via `_pi_settings`,
  store-owned via `pi_extension_install.plan/apply` → project-scope lock
  bookkeeping (`add_entry` / `remove_entry` on the project lock only).
- Raises the existing typed errors (`pi_extension_install.InstallError`,
  `_pi_settings.PiSettingsError`). No new exception types.
- **npm fix lands here.** `uninstall` removes `packages[]` entries by **package
  identity**, not exact string. See below.
- **store-owned stays correct.** Global keeps the library lock entry; project-scope
  lock bookkeeping unchanged. The `if scope == "project"` prune lives here now.

### npm identity matching: `_pi_settings.remove_package_by_identity`

New function in `_pi_settings.py` (the existing exact-match `remove_package` is
**unchanged** and retained for any other caller):

```python
def remove_package_by_identity(spec_or_slug: str, *, scope, home, project) -> None
```

- Normalize an npm spec/slug to a bare package identity: strip a leading scheme
  (`npm:`), then strip a trailing `@version` **without** eating the leading `@` of a
  scoped name (`@scope/name@1.2.3` → `@scope/name`; `foo@1.2.3` → `foo`;
  `npm:@scope/name` → `@scope/name`).
- Remove **every** `packages[]` entry whose normalized identity equals the target's
  identity, at the given scope. Atomic write (reuses `_write_atomic`). No-op if the
  file is missing or nothing matches. Fail-loud on malformed settings.json
  (`PiSettingsError`), same as the rest of the module.
- `pi_extension_ops.uninstall` uses this for npm rows. `install` continues to use
  `add_package` with the lock's `entry.source` verbatim (no behaviour change).

### CLI wrappers become thin

`install_cmd` / `uninstall_cmd` parse flags via `scope_and_roots`, call
`pi_extension_ops.{install,uninstall}`, convert typed errors to `ClickException`,
and `click.echo` the same success lines as today. No user-visible CLI change.

### TUI delegates

`_apply_pi_pending` (`app.py`) deletes its inline `entry.source_type` / `plan` /
`apply` / project-lock block (the `app.py:783-840` region) and calls
`pi_extension_ops.install(...)` / `pi_extension_ops.uninstall(...)` per pending
toggle, keeping its existing `ok` / `failed` / `errors[]` accounting,
`clear_pending()`, and `_refresh_pi_view()`. It still reads the global library lock
once up front only to skip untracked slugs (rows with no lock entry are
non-interactive); the per-entry source/lock logic moves entirely into the core.

## Data flow — global npm deselect (the reported repro)

```
uncheck global cell
  → ctrl+s → _apply_pi_pending
  → pi_extension_ops.uninstall(slug, scope="global", home, project=None)
  → _pi_settings.remove_package_by_identity(entry.source, scope="global", ...)
  → matching packages[] entries removed from ~/.pi/agent/settings.json
  → _refresh_pi_view → build_inventory reads no package
  → global_loaded = False → row stays unchecked ✓
```

## Error handling

Unchanged posture. Core raises `InstallError` / `PiSettingsError`; CLI wrappers
convert to `ClickException`; the TUI catches both and tallies into `errors[]`
exactly as today. Fail-loud on malformed settings.json preserved.

## Testing (RED-first, per DoD)

Each test is written to fail against the current code before the fix, then pass
after.

1. **`pi_extension_ops` unit — global npm uninstall with a drifted `packages[]`
   entry.** Lock stores `npm:foo`; `settings.json` has `npm:foo@1.2.3` (or `foo`).
   RED today (entry survives via exact-match no-op); GREEN after identity matching.
2. **`pi_extension_ops` unit — global store-owned uninstall.** After uninstall the
   `~/.pi/agent/extensions/<slug>` symlink is gone AND the global library lock
   entry is **retained** (distinguishes uninstall from remove).
3. **`_pi_settings` unit — `remove_package_by_identity` normalization.** Scoped
   (`@scope/name@1`), unscoped (`foo@1`), `npm:`-prefixed, and no-match cases.
4. **CLI — `pi-extension uninstall <slug> -g`** for both origins, asserting on-disk
   `settings.json` / symlink state (round-trips through the real command).
5. **TUI round-trip — global deselect → apply → refresh.** `build_pi_rows` shows
   `global_loaded=False` for both origins after Apply (the revert is the regression
   this guards). RED proven against the current `_apply_pi_pending`.

## Out of scope

- Project-scope deselect (works today — no behaviour change; existing tests stay
  green).
- Other asset kinds (skills, agents, instructions).
- Redesigning the inventory's loaded-state derivation.
- The `remove` verb and `remove_package`'s exact-match semantics (both retained
  as-is).

## Files touched

- `src/agent_toolkit_cli/pi_extension_ops.py` — **new**: `install` / `uninstall`
  core.
- `src/agent_toolkit_cli/_pi_settings.py` — **add** `remove_package_by_identity`
  (and the private normalizer); `remove_package` unchanged.
- `src/agent_toolkit_cli/commands/pi_extension/install_cmd.py` — thin wrapper over
  the core.
- `src/agent_toolkit_cli/commands/pi_extension/uninstall_cmd.py` — thin wrapper over
  the core.
- `src/agent_toolkit_tui/app.py` — `_apply_pi_pending` delegates to the core.
- `tests/` — RED-first regressions listed above.
