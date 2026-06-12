# pi-extension half-dir: heal on add, surface in doctor (#347)

**Issue:** #347 · **Tier:** standard · **Date:** 2026-06-12
**Decided with orchestrator (3 forks):** both directions (add-side self-heal +
doctor finding); heal = rmtree + re-clone reconciling the lock; trigger =
`canonical.exists() AND NOT is_git_repo` (covers empty + half dirs); the
existing valid-repo source-mismatch refuse runs FIRST and is unchanged.

## Problem

`pi_extension_add.add()` early-returns success whenever `canonical.exists()`
(`pi_extension_add.py:99-110`, the "already present" idempotency guard). The
guard only tests directory existence, not validity. A partially-failed
cleanup — the failed-checkout path runs `shutil.rmtree(canonical,
ignore_errors=True)` (`pi_extension_add.py:133`), which on a transient FS
error can leave a **half-deleted, non-git-repo directory** — makes the NEXT
`add` of the same slug report success over a broken store copy. The stale lock
entry (written on the prior successful-looking attempt, or pre-existing)
persists, so nothing self-corrects.

The doctor has the adjacent machinery but a matching blind spot: `_check_slug`
(`pi_extension_doctor.py:120-153`) emits `missing_canonical` only when
`canonical` does **not** exist, then branches on `is_git_repo(canonical)` for a
dirty-tree check — but a canonical that exists and is **not** a git repo falls
through every branch silently. So neither `add` nor `doctor` notices a half-dir.

This was a #330-waived low-likelihood FYI (anchor 50); filed so it isn't lost.

## Design

### 1. add() — heal a non-repo canonical instead of trusting it

Reorder the `if canonical.exists():` block so validity is checked before
idempotent success is declared:

```python
canonical = library_pi_extension_path(ext_slug, env={})
if canonical.exists():
    if skill_git.is_git_repo(canonical):
        # Valid store copy — verify source matches, else refuse (unchanged).
        lock = read_lock(lock_path)
        existing = lock.skills.get(ext_slug)
        requested = parsed.owner_repo or parsed.url
        if existing is not None and existing.source != requested:
            raise AddError(
                f"{ext_slug}: library already has a different source "
                f"({existing.source!r}); run `pi-extension remove {ext_slug}` first"
            )
        return ext_slug  # idempotent over a VALID repo
    # #347: exists but is NOT a git repo — a half-written/empty dir left by a
    # partially-failed cleanup. Treat as not-present: remove it and fall
    # through to the normal clone path (which rewrites the lock entry).
    shutil.rmtree(canonical, ignore_errors=True)
    # fall through — no early return
```

Key properties:
- **Idempotent success only over a valid repo.** A non-repo dir is never
  trusted.
- **Source-mismatch refuse is preserved and runs first** — only inside the
  `is_git_repo` arm. A valid repo with the wrong remote still refuses; it is
  NEVER silently re-cloned (skill-add parity).
- **Self-heal = rmtree + fall through.** The existing clone path below
  re-clones and rewrites the lock entry, so a re-add over a half-dir behaves
  exactly like a fresh add. Reuses the codebase's own cleanup idiom
  (`shutil.rmtree(..., ignore_errors=True)`).
- **Empty dirs are healed too** — an empty dir is also `NOT is_git_repo`, and
  it would otherwise early-return success over nothing.
- **npm rows are untouched** — they never reach this block (the npm branch
  returns at `pi_extension_add.py:78-85`).

### 2. doctor — a `half_dir` finding for non-repo canonicals

Add `"half_dir"` to the `FindingType` literal
(`pi_extension_doctor.py:41-49`). In `_check_slug`, widen the
store-owned-canonical check: when `canonical.exists()` is true but
`is_git_repo(canonical)` is false, emit a `half_dir` finding **before** the
dirty-tree branch:

```python
if not canonical.exists():
    findings.append(Finding(finding_type="missing_canonical", ...))  # unchanged
    return findings
if not skill_git.is_git_repo(canonical):
    findings.append(Finding(
        finding_type="half_dir", slug=slug, scope=scope, path=canonical,
        detail=(
            f"store copy at {canonical} exists but is not a git repo "
            f"(partial/failed clone). Source: {getattr(entry, 'source', '?')}"
        ),
        fix_action=_make_reclone_action(slug=slug, entry=entry, force=True),
    ))
    return findings  # can't check projection/dirty-tree over a broken store
# ... existing is_git_repo dirty-tree branch unchanged
```

### 3. _make_reclone_action — must clear a non-repo dir before cloning

**Load-bearing correction (verified in source):**
`_make_reclone_action._apply()` opens with `if canonical.exists(): return  #
idempotent` (`pi_extension_doctor.py:362-363`). That guard is correct for
`missing_canonical` (the dir is gone) but **wrong for `half_dir`** — the dir
exists, so the fix would no-op and never repair it.

Add a `force: bool = False` parameter to `_make_reclone_action`. When `force`
is set, `_apply()` rmtrees a pre-existing canonical before cloning instead of
early-returning:

```python
def _make_reclone_action(*, slug: str, entry: object, force: bool = False) -> FixAction:
    ...
    def _apply() -> None:
        if canonical.exists():
            if not force:
                return  # idempotent (missing_canonical: dir is gone, this is a race guard)
            shutil.rmtree(canonical, ignore_errors=True)
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(...)
        ...  # pin logic unchanged
```

`missing_canonical` keeps calling `_make_reclone_action(slug=, entry=)`
(force defaults False — behavior unchanged). `half_dir` calls it with
`force=True`. The `shell_preview` text needs no change (it already shows the
clone command; the rmtree is an internal precondition).

## Non-goals / out of scope

- Re-validating canonical integrity beyond `is_git_repo` (e.g. checking the
  remote URL matches the lock for a VALID repo — that is the existing
  source-mismatch refuse, kept as-is; deeper integrity audits are doctor's
  separate concern).
- Healing valid-repo-wrong-remote by re-cloning (explicitly refused, not
  healed — skill-add parity; deleting a deliberately-swapped store is unsafe).
- Any change to npm (registry-tracked) rows.
- Touching the failed-checkout cleanup that CREATES the half-dir — the fix is
  to tolerate the leftover, not to make rmtree infallible (FS-transient
  failures are inherent).

## Test surface

All RED-first (TDD):

1. **add heals a half-dir:** seed `canonical` as a non-repo dir (e.g.
   `mkdir` + a stray file) + a stale lock entry; `add()` the same source →
   returns the slug, `canonical` is now a valid git repo, lock entry rewritten.
   (Use a `file://{bare}` source for a hermetic clone, per the #330 test
   vehicle.)
2. **add heals an empty dir:** `canonical` is an empty dir → same outcome.
3. **add still idempotent over a valid repo:** existing behavior unchanged
   (regression guard).
4. **add still refuses source-mismatch over a valid repo:** existing refuse
   path fires; the valid repo is NOT rmtree'd.
5. **doctor emits half_dir:** non-repo `canonical` + lock entry → one
   `half_dir` finding, no `missing_canonical`, no `dirty_tree`.
6. **doctor missing_canonical unchanged:** absent `canonical` → still
   `missing_canonical` (regression guard).
7. **half_dir fix_action repairs:** apply the fix over a non-repo dir →
   `canonical` becomes a valid git repo (proves the `force=True` rmtree;
   RED-prove against the un-forced `_apply` which no-ops on `exists()`).
8. **doctor skips npm rows:** an npm lock entry never yields a `half_dir`
   (no canonical).

## Links

- Source: #330 critical-review waived FYI (anchor 50); cleanup paths added in
  PR #343 (`pi_extension_add.py` failed-checkout block,
  `pi_extension_doctor.py` `_make_reclone_action`).
- Parity: skill-add's source-mismatch refuse posture.
- Adjacent: #346 / PR #386 (pi-extension push/status, same module area, merged
  first to avoid conflicts).
