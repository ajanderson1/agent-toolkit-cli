# instructions doctor: backup-then-symlink fix for unmanaged files when canonical is populated — design

**Issue:** #375 · **Tier:** standard (multi-file: doctor_cmd + tests; no deep
triggers — lock schema unchanged, no new asset kind) · **Date:** 2026-06-11

## Problem

`instructions doctor`'s `unmanaged` finding (`commands/instructions/doctor_cmd.py`,
`_unmanaged_finding`) only offers its adopt fix when the canonical `AGENTS.md`
is missing or empty (`adoptable = not canonical.exists() or size == 0`,
doctor_cmd.py:76). Once one file has been adopted, every other unmanaged
harness file at that scope degrades to a report-only finding ("AGENTS.md
already exists — adopt skipped"). This is the common multi-harness situation
at global scope (distinct slots: `~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`,
`~/.augment/CLAUDE.md`, …); the user must finish the job by hand
(`mv <file> <file>.pre-adopt.bak && instructions install --harness <h>`).

Live repro 2026-06-11: `doctor --scope global` adopted `~/.claude/CLAUDE.md`,
left `~/.gemini/GEMINI.md` unmanaged with no offered fix.

## Decision (AJ, recorded in issue body 2026-06-11)

**Backup-then-symlink**, chosen over identical-content-only and over
backup+append-merge. Content is never merged — the existing "content merge is
out of scope" stance stands; the finding/fix text points at the `.bak` so the
user can reconcile manually.

When canonical `AGENTS.md` exists with content, the `unmanaged` finding offers
a **replace-with-pointer** fix-action in the same y/N/q loop:

1. Rename the unmanaged file to `<name>.pre-adopt.bak` beside itself
   (e.g. `~/.gemini/GEMINI.md.pre-adopt.bak`). Never clobber, never silently
   discard: if the `.bak` path already exists, fail loudly with nothing
   changed. (`Path.rename` silently replaces an existing target on POSIX, so
   an explicit existence check is required before the rename.)
2. Add the harness to the existing `AGENTS.md` lock entry (merge-sorted, same
   `add_entry` pattern as the adopt fix; creates the entry if the lock has
   none) and write the lock.
3. Reconcile via `instructions_install.apply(...)` so the slot gets its
   symlink.
4. Same rollback contract as the adopt fix (#337): on ANY apply failure —
   not just domain errors — undo the symlink apply() laid at our slot,
   restore the user's file from the `.bak`, restore the prior lock (or delete
   it if it didn't exist). Never leave a lying lock.

### Detail decisions

- **`.bak` naming** (resolves the issue's open `> needs:`): `<name>.pre-adopt.bak`
  stands. The only other backup convention in the codebase is skill_doctor's
  `.bak-doctor-<stamp>` for *directories* — different namespace, no collision.
  No timestamp: a pre-existing `.bak` means a previous adopt already ran here,
  and silently stacking backups would hide that; fail-loudly is the convention
  (`errors.md`).
- **Harness attribution** reuses `_adopt_harness_for` unchanged: at project
  scope the shared `{PROJECT}/CLAUDE.md` slot records `claude-code`; at global
  scope each harness owns its distinct slot (augment's global CLAUDE.md
  records `augment`).
- **Guard re-assertion at apply time** (mirrors the adopt fix's re-check): the
  fix was constructed against a populated canonical; if canonical has since
  vanished or emptied, the situation has changed — raise a ClickException
  telling the user to re-run doctor, touching nothing.
- **Structure**: `_unmanaged_finding` becomes a dispatcher — canonical
  missing/empty → existing adopt fix (rename-to-canonical); canonical
  populated → new backup-then-symlink fix. Both fixes share the
  rollback shape; the adopt fix's code is not changed behaviourally.
- **Finding & fix text**: the finding message stays `unmanaged: real file at
  <pointer> is not in the lock`; the `shell_preview` mirrors the manual
  workaround (`mv <name> <name>.pre-adopt.bak && instructions install
  --harness <h>`); on success the loop's output names the `.bak` so the user
  knows where their content went and that merging it is theirs to do.

## Behaviour matrix

| State at slot | Canonical | Today | After |
|---|---|---|---|
| real file, not in lock | missing/empty | adopt fix (rename → canonical) | unchanged |
| real file, not in lock | populated | report-only | **backup-then-symlink fix** |
| real file, harness wanted in lock | any | `conflict` finding | unchanged |
| `.pre-adopt.bak` already present | populated | n/a | fix fails loudly, nothing changed |

Declining (`N`) keeps it a reported finding; `--no-fix` and non-TTY behaviour
and exit-code semantics (any skipped finding → exit 1) are unchanged.

## Test surface

Mirror the #337 adopt tests (`tests/test_cli/test_instructions_cli.py`):

- Populated canonical + unmanaged real file → fix offered; `y` leaves
  `.pre-adopt.bak` with original content, slot symlinked to canonical, harness
  merged into the lock entry, doctor clean on re-run, exit 0.
- Pre-existing `.pre-adopt.bak` → fix fails loudly; original file, canonical,
  and lock all untouched; exit ≠ 0.
- Mid-apply failure (monkeypatch `instructions_install.apply` on the source
  module, both the plain-failure and symlink-then-fail variants) → full
  rollback: file restored from `.bak`, `.bak` gone, prior lock restored
  verbatim, no orphan symlink.
- Global scope (the live repro shape: claude-code already managed,
  `~/.gemini/GEMINI.md` unmanaged) and augment-global-slot attribution.
- Project-scope shared-slot rule unaffected (`CLAUDE.md` → `claude-code`).
- Declining `N` → finding reported, nothing mutated, exit 1.
- **Existing test updated, deliberately**:
  `test_doctor_unmanaged_does_not_clobber_existing_agents` asserts today's
  report-only behaviour (`y` → exit 1, nothing changes). Its protection
  intent ("y must not destroy either file") is preserved by the new
  assertions (canonical content untouched, original content intact in the
  `.bak`); its report-only expectation is the behaviour this issue removes.

## Acceptance criteria

(as in the issue body)

1. Doctor at a scope with canonical populated + unmanaged real file at a
   harness slot offers the backup+symlink fix (no longer report-only).
2. Applying it leaves: `<name>.pre-adopt.bak` with the original content, slot
   symlinked to canonical, harness present in the lock entry, doctor clean on
   re-run.
3. Pre-existing `.pre-adopt.bak` at the target path → fix fails loudly,
   nothing changed.
4. Mid-apply failure rolls back fully (file restored, lock restored, no orphan
   symlink) — mirror the existing adopt rollback tests.
5. Works at both scopes; project-scope shared-slot rule (`_adopt_harness_for`)
   unaffected.
6. Declining (`N`) keeps it a reported finding; exit-code semantics unchanged.

## Out of scope

- Content merge between the unmanaged file and canonical (standing stance).
- Asset-type alignment audit (instructions vs skill/agent doctor convergence)
  — issue body explicitly defers it.
- Doctor reaping/cleanup of `.pre-adopt.bak` files (they are the user's to
  reconcile and delete).
