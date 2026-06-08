# Design — `instructions doctor` adopts an unmanaged instruction file

**Issue:** #337 · **Type:** feat · **Milestone:** v4.0.0

## Problem

In a project dir containing only a real `CLAUDE.md` (and a `.pi/` folder), `agent-toolkit-cli instructions doctor` prints `clean — no findings at this scope`. That is misleading: there's an obvious, adoptable instruction file sitting outside management. Today `doctor` is a pure consistency-checker over the lock — it reports **orphan** (lock says ON, canonical gone), **conflict** (lock says ON, pointer is a real file / foreign symlink), and **stray** (a symlink at a slot, pointing at canonical, not in the lock). It never scans the directory for an *unmanaged real file*, and there is no adopt path at all.

## Goal

`instructions doctor` (project **and** global scope) detects a real, unmanaged instruction file at a known pointer slot — a real file (not a symlink) that is **not** recorded in the lock — and surfaces it as a **new finding type** distinct from orphan/conflict/stray. When found, and there is no non-empty canonical `AGENTS.md`, doctor offers to **adopt** it: rename the real file → `AGENTS.md` (byte-for-byte), then drive the existing `install` path so the original slot (e.g. `CLAUDE.md`) becomes a symlink → `AGENTS.md`, writing the lock entry. The user extends to other harness pointers later via the existing TUI / `install`.

## Approach (and the one real design decision)

**The decision: reuse the existing `Finding` + `fix_action` interactive-doctor pattern, do not invent a new one.**

`skill/doctor_cmd.py` and `pi_extension/doctor_cmd.py` already implement the exact y/N/q prompt loop this feature needs, *including* the non-TTY guard the issue's DoD requires:

```python
try:
    ans = click.prompt("  apply?", default="N", show_default=False,
                       type=click.Choice(["y", "N", "q"], case_sensitive=False))
except (click.Abort, EOFError, OSError):
    click.echo("\n  (no input available — stopping; nothing applied)")
    quit_loop = True; skipped += 1; continue
```

The instructions doctor today builds a `list[str]` and calls `ctx.exit(1)`. We migrate it to the same `Finding(message, fix_action)` shape used by its sibling doctors:

- The three existing findings (orphan / conflict / stray) become `fix_action=None` entries — **report-only, behaviour unchanged**.
- The new **unmanaged** finding carries a `fix_action` that performs the adopt.
- The prompt loop, summary line, and `ctx.exit(1)`-on-skipped semantics are copied from `skill/doctor_cmd.py` verbatim.

This gives us, for free: the `--no-fix` flag (report-only), correct non-TTY behaviour (no silent mutation — the `except` falls through to `quit_loop`, nothing applied, still exits 1), and a UX consistent with the other two doctors. Inventing a bespoke prompt would diverge from two existing call sites for no benefit.

### Detection rule (the new fourth scan block)

After the orphan/conflict/stray blocks, scan every `SUPPORTED_HARNESSES` slot:

```
pointer = _pointer_path(harness, scope, project_root, home)   # try/except ValueError: continue  (replit has no global slot)
unmanaged IF:
    pointer.exists() and not pointer.is_symlink()      # a real file, not a managed symlink
    and pointer not in conflict_paths                  # a real file at a *wanted* slot is already a "conflict"; don't double-report
    and adoptable_canonical()                          # not pointer in already-emitted unmanaged paths (dedupe shared slot)
```

where `adoptable_canonical()` ⇔ `not canonical.exists() or canonical.stat().st_size == 0`. If a non-empty `AGENTS.md` already exists, **we still report the unmanaged file** (it's a real finding) but as `fix_action=None` with a detail explaining the content-merge case is out of scope — never clobber.

### Two traps the detection must handle (from scout brief)

1. **Shared slot.** `augment` and `claude-code` both map to project-root `CLAUDE.md`. Iterating harnesses yields the same pointer path twice → two findings → the second adopt's rename fails with `FileNotFoundError`. **Dedupe by resolved pointer path**: emit at most one unmanaged finding per unique slot path. The finding message names the slot file, not the harness.
2. **Conflict vs unmanaged are mutually exclusive.** A real file at a slot a *wanted* harness claims is already a **conflict**. Track `conflict_paths: set[Path]` while building conflicts and exclude them from the unmanaged scan, so a slot is reported by exactly one rule.

### Adopt fix_action (mirrors install's contract, ordered to be rollback-safe)

The closure captures `scope`, `project_root`, `home`, `canonical`, `lock_path`, `pointer`, and the adopting harness (`claude-code` for the `CLAUDE.md` slot — derive from the slot, default `claude-code`). Steps, in this exact order so a mid-flight failure never leaves a lying lock or a lost file:

1. Re-assert `adoptable_canonical()` (guard against a race / a second finding) — abort the action with a clear message if a non-empty `AGENTS.md` appeared.
2. `prior = read_lock(lock_path)`; `prior_existed = lock_path.exists()`.
3. **Rename** `pointer → canonical` (`pointer.rename(canonical)`) — byte-for-byte, no copy. Canonical now exists, so `apply()` won't raise `CanonicalMissingError`.
4. Build `new = add_entry(prior, "AGENTS.md", InstructionsLockEntry(scope=scope, source="AGENTS.md", harnesses=[harness]))`. `write_lock(lock_path, new)`.
5. `instructions_install.apply(scope=scope, project_root=project_root, home=home)` — re-creates the slot as a symlink → canonical.
6. On `(CanonicalMissingError, PointerConflictError)`: **roll back** — rename `canonical → pointer` (restore the original real file), then `write_lock(lock_path, prior)` if `prior_existed` else `lock_path.unlink(missing_ok=True)`; re-raise as the fix's failure (the loop's `except Exception` already prints `fix failed: …` and counts it skipped).

Rename-before-lock is deliberate: if the lock were written first and the rename failed, the lock would claim a canonical that doesn't exist.

## Out of scope

- **No standalone `instructions adopt` command** — adoption is offered inline from `doctor`. A separate verb can come later.
- **No content merging** when a non-empty `AGENTS.md` already exists — that case is reported but not auto-fixed (a follow-up).
- **No change** to the 7-harness symlink matrix or the native-reader set.
- No multi-harness adopt in one go — adopt establishes the canonical + the one slot we found; the user fans out to other harnesses via existing `install`/TUI.

## Definition of done

- New **unmanaged** finding emitted by `doctor` at both project and global scope when a real, non-symlink, lock-unrecorded file sits at a known slot.
- Adopt (on `y`): renames the file to `AGENTS.md`, installs the slot as a symlink → canonical, writes the lock; honours write-lock → apply → rollback; a re-run of `doctor` is `clean`.
- Non-empty `AGENTS.md` present → unmanaged file reported but **not** auto-adopted (no clobber).
- `--no-fix` and non-TTY runs: detection reports the finding and exits non-zero, but **no mutation** occurs.
- Tests (project + global): bare `CLAUDE.md` → unmanaged finding (RED today); `y` adopts and converges (`CLAUDE.md` is a symlink → `AGENTS.md`, lock has the entry); round-trip `doctor` clean; `--no-fix` leaves the file untouched; non-empty-`AGENTS.md` guard does not clobber; shared-slot dedupe yields exactly one finding.

## Risk notes

- Migrating the doctor from `list[str]` to `Finding` objects touches the three existing findings' output format. Keep their printed text equivalent (existing tests may assert on substrings like `orphan:`/`conflict:`/`stray:`); preserve those tokens in the new `Finding.message`/detail.
- `read_lock` on a missing file returns an empty lock (no raise) — safe.
- `home` is `None` for project scope throughout; pass it straight through to `apply()` (install does the same).
