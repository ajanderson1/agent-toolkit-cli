# pi-extension push/status on SHA-pinned entries — design

**Issue:** #346 · **Tier:** standard (plan touches 3 source files + tests; no deep trigger) · **Date:** 2026-06-12

## Problem

#330 (PR #343, merged 6635496) taught `pi-extension update`/`reset` to skip
SHA-pinned entries — a store-owned extension whose lock `ref` is a raw commit
SHA sits at a detached HEAD on that pin, and updating/resetting it is
meaningless. Both verbs now emit `<slug>: pinned to <sha> — skipping (remove
and re-add to change the pin)` and continue. `push` and `status` were an
explicitly documented out-of-scope limitation of #330; their behaviour on a
pinned entry is undefined and untested.

Verified on main @ 1338e35 (line numbers below are HEAD-relative):

- **`push`** (`commands/pi_extension/push_cmd.py:81`) calls
  `skill_git.resolve_ref(entry.ref, canonical)` then `divergence(...,
  ref=ref)` against `origin/<ref>` where `ref` is the raw SHA. There is no
  `origin/<sha>` ref, so this errors or reports nonsense; worse, a git error
  in the loop sets `rejected = True` and the batch exits 1 — one pinned
  entry can poison an otherwise-clean `push`.
- **`status`** (`commands/pi_extension/status_cmd.py`) reads `build_inventory`
  and prints `<slug>\t<origin>\t<loaded-scopes>`. A pinned entry is
  indistinguishable from an unpinned store-owned one — the user has no signal
  that the extension is frozen at a pin.

`#345` (lock schema pin/tip split) is still **open**, so this work stands
alone: detection reuses the existing `looks_like_sha()` heuristic rather than
a future schema field.

## Decisions (AJ, 2026-06-12, via /aj-issue interview)

1. **Detection: `looks_like_sha(entry.ref)`** — the same heuristic
   `update`/`reset` already use (`pi_extension_add.py:36`). No dependency on
   #345. When #345 lands it swaps the detection source in one line per site;
   the user-facing surfaces are unchanged.
2. **`status` learns the pin via `InventoryRecord`** — add a `pinned_sha`
   field, populated in `build_inventory`. Keeps `status_cmd` reading a single
   source (the inventory) and makes the inventory pin-aware for future
   consumers (doctor/list).
3. **`status` shows the pin as a trailing 4th column** — `<slug>\t<origin>\t
   <loaded>\t<pin>`. Orthogonal to load-scope (a pinned extension can still be
   loaded), so the existing loaded-scopes column stays intact and scripts
   parsing field 3 keep working. The column uses the compact `pinned:<sha7>`
   token **deliberately** — a machine-parseable single field, intentionally
   NOT the prose `pinned to <sha7> — skipping` message the action verbs
   (push/update/reset) emit. The two surfaces describe the same state in two
   registers (terse column vs. prose action-log) on purpose; do not unify
   them. Blast-radius check: **no in-repo consumer parses `status` stdout**
   (verified — the TUI calls `build_inventory` directly; no test, doctor, or
   script tab-splits the output), so moving the field count from 3 to 4 is
   internally safe. If the tab format is ever treated as a stable external
   contract, the 3→4 change belongs in the CHANGELOG/README for downstream
   parsers.

## Design

### Unit 1 — `push` skip (mirror of #330)

In `commands/pi_extension/push_cmd.py`, inside the `for slug in targets`
loop, after the existing `not in lock` → `npm row` → `copy-mode` guards and
**before** the `resolve_ref`/`divergence` calls (current line 81):

```python
if looks_like_sha(entry.ref):
    click.echo(
        f"{slug}: pinned to {entry.ref[:7]} — skipping "
        f"(remove and re-add to change the pin)"
    )
    continue
```

- **No `rejected = True`.** A pin is a benign no-op (nothing to push from a
  detached pin), not a rejection. The skip exits 0 and does not poison a
  batch — this is the headline fix vs. today's divergence-error-sets-rejected
  path. Contrast the `npm row` guard, which DOES set `rejected` (an npm row is
  a user error: you asked to push something unpushable).
- Import `looks_like_sha` from `pi_extension_add` (the module `update_cmd`
  and `reset_cmd` already import it from).
- Placement is before `resolve_ref`, so the raw SHA never reaches the git
  divergence machinery.
- **The skip is unconditional w.r.t. working-tree state.** It fires for every
  pinned entry, including a pinned checkout the user has locally edited or
  committed — those local changes are intentionally **unreachable via push**.
  This is by design, not a regression: the existing `_push_via_pr` path is
  already broken for a pinned entry (`gh pr create --base <raw-sha>` is
  invalid), so no working capability is lost. To publish work made on a pinned
  checkout, the user must `remove` and re-add (un-pinning to a branch) first —
  the same escape hatch the skip message names. If #345 later gives pins a
  tracked tip, a real publish path can be reconsidered (out of scope here).

### Unit 2 — `InventoryRecord.pinned_sha`

In `pi_extension_inventory.py`:

```python
@dataclass
class InventoryRecord:
    slug: str
    origin: Origin
    source: str
    global_loaded: bool = False
    project_loaded: bool = False
    pinned_sha: str | None = None   # NEW — raw SHA when entry.ref looks_like_sha
```

In `build_inventory`'s lock pass (`pi_extension_inventory.py:107-117`), set
`pinned_sha` from the lock entry. The record is created via `setdefault`, so
the field must be set **both** at construction and on the refine path — a slug
present in both the global and project locks is constructed from the first
scope's `entry` and refined on the second, and the pin can differ between
scopes (e.g. pinned globally, unpinned in a project override). Mirror how
`source` is already refreshed on every iteration:

```python
for slug, entry in lock.skills.items():
    origin: Origin = "npm" if entry.source_type == "npm" else "store-owned"
    pinned_sha = entry.ref if looks_like_sha(entry.ref) else None
    rec = by_slug.setdefault(
        slug,
        InventoryRecord(slug=slug, origin=origin, source=entry.source,
                        pinned_sha=pinned_sha),
    )
    if rec.origin != "store-owned" or origin == "store-owned":
        rec.origin = origin
    rec.source = entry.source
    rec.pinned_sha = pinned_sha   # refresh like source, so the last lock pass wins
```

This matches the existing precedence (project lock processed after global,
project's `source`/`origin`/`pin` win). npm and untracked rows leave
`pinned_sha=None` (the default — the loose/untracked passes never touch it).
Import `looks_like_sha` into this module.

### Unit 3 — `status` trailing column

In `commands/pi_extension/status_cmd.py`, the output line becomes:

```python
pin = f"pinned:{r.pinned_sha[:7]}" if r.pinned_sha else ""
click.echo(f"{r.slug}\t{r.origin}\t{loaded}\t{pin}")
```

The `loaded` field is computed exactly as today (unchanged). A non-pinned row
prints an empty 4th field (trailing tab + nothing), so every row has the same
column count — scripts can split on `\t` and read field 4 uniformly.

## Out of scope

- The `skill`/`agent` push/status families. This is the pi-extension-specific
  #330 follow-up; #330 only touched pi-extension.
- The #345 lock-schema pin/tip split itself. This issue is forward-compatible
  with it (one-line detection swap per site) but does not implement it.
- Changing `update`/`reset` — already handled by #330.

## Test surface

Hermetic, via the proven `_seed_pinned_entry` + `file://{bare}/tree/{sha}`
idiom (`tests/test_cli/test_cli_pi_extension_lifecycle.py:133`), HOME-isolated
sandbox:

1. **`push` over a pinned entry** → output contains `pinned to <sha7>`, exit
   **0** (the batch-safety guarantee), and no push/PR side effects.
2. **`push` batch isolation** → a pinned entry alongside a pushable/other
   entry does not flip the exit code to 1 on the pinned one's account
   (regression guard for the no-`rejected` decision).
3. **`status` over a pinned entry** → line has a trailing `pinned:<sha7>`
   field AND the loaded-scope column is still present/correct.
4. **`status` non-pinned regression** → store-owned non-pinned and npm rows
   print an empty 4th field (no `pinned:` token), column count unchanged.
5. Existing `update`/`reset` pinned tests stay green (untouched code).

## Acceptance criteria

1. `pi-extension push` over a SHA-pinned entry: informational
   `pinned to <sha7> — skipping` message, exit 0, no batch poisoning, no git
   divergence error.
2. `pi-extension status` over a SHA-pinned entry: reports the pin explicitly
   as a trailing `pinned:<sha7>` column, with no phantom ahead/behind and the
   load-scope column preserved.
3. Detection uses `looks_like_sha(entry.ref)` (no #345 dependency);
   `InventoryRecord` carries `pinned_sha`.
4. Hermetic tests cover push-pinned (skip + exit 0 + batch isolation) and
   status-pinned (trailing column + preserved load-scope), plus a non-pinned
   regression for each.
5. Full suite green (modulo the 2 known HOME-isolation environment failures).
