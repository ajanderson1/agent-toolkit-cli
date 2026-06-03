# Design: agent add orphan-canonical fix (#313)

**Date:** 2026-06-02
**Issue:** #313
**Branch:** fix/313-agent-add-orphan-canonical

---

## Problem

`agent add SOURCE` (no `--slug`) clones the source repository into
`agents/<repo-name>/` before validating that the derived `<slug>.md`
content file exists at the repo root. When the repo name does not match
the actual content file name the validation fails — correctly — but the
clone already exists on disk with no lock entry. Both `agent remove` and
`agent doctor` operate over lock entries, so neither command can see or
reclaim the orphaned directory. The user is left with an unreachable stray
directory in their agent library.

### Root-cause sequence (from add_cmd.py)

1. `final_slug = slug or _derive_slug(parsed)` — slug derived from repo name
2. `canonical = library_agent_path(final_slug)` — path computed
3. `if not canonical.exists(): skill_git.clone(...)` — **clone happens**
4. `if not content_file.exists(): raise ClickException(...)` — validation
   raises AFTER clone — orphan left behind

### Why the clone precedes the validation

The inline comment in add_cmd.py documents the intent: a re-run with the
correct `--slug` should reuse the already-cloned directory (idempotent
recovery path). This intent is valid and must be preserved.

### What's missing

A. **Cleanup on fresh-clone failure.** If `add` clones a directory as part
   of *this invocation* and then validation fails, the just-created
   directory should be removed before raising. Only remove what *this call*
   created — if the canonical already existed before the call (pre-existing
   idempotent-reuse case), do not touch it.

B. **Doctor orphan-canonical detection.** Doctor currently iterates lock
   entries and checks their canonical directories. It does not walk the
   library directory to find canonicals that have no lock entry. Adding an
   `orphan-canonical` check makes the library self-healing regardless of
   *how* an orphan was created (partial add, interrupted clones, manual
   surgery).

---

## Proposed changes

### Change 1 — add_cmd.py: cleanup on fresh-clone failure

Track whether `clone()` was called in this invocation with a boolean flag
`fresh_clone`. If validation raises and `fresh_clone is True`, call
`shutil.rmtree(canonical)` before re-raising. This is narrowly targeted:

- `fresh_clone = False` if the canonical already existed (the `exists()`
  guard was true) — so the pre-existing idempotent path is untouched.
- `fresh_clone = True` only if the clone ran inside this invocation.
- The rmtree is inside the `if fresh_clone` guard, so a pre-existing
  (possibly partially-populated from a previous add with a different slug)
  canonical is never removed.

### Change 2 — doctor_cmd.py: orphan-canonical detection

After iterating lock entries, walk `library_agent_path("").parent` (the
library base directory) for immediate child directories. Any child whose
`basename` is not a key in the lock is an `orphan-canonical`. Report it
as kind `"orphan-canonical"` with a fix action: `shutil.rmtree` the
directory.

Implementation notes:
- Walk is shallow (1 level deep) — the library directory layout is
  `agents/<slug>/` with no nested slugs.
- Only report directories, not files — the lock file itself lives in the
  library base and must be ignored.
- When `slugs` is specified (targeted run), the orphan-canonical check is
  skipped (targeted run implies the user already knows which slug to check).
- The fix action for `orphan-canonical` sets `shell_preview` to
  `f"rm -rf {canonical}"` and `apply` to `shutil.rmtree(canonical)`.

---

## Acceptance criteria

1. `agent add <source>` (no `--slug`) that derives a slug whose `.md` file
   is absent leaves **no** stray directory in the library afterward.
2. The idempotent re-run path — `add` again with the correct `--slug` —
   still works. The cleanup only fires on a fresh clone.
3. `agent doctor -g` on a library with a stray canonical (no lock entry)
   reports `orphan-canonical` and offers to remove it.
4. `agent doctor -g` on a clean library still reports "all clean".
5. Tests cover: failed-add leaves no orphan, doctor detects and can fix
   orphan-canonical.

---

## Out of scope

- The #303 uninstall-vs-remove contract is unrelated and unchanged.
- No changes to `agent remove`, `agent install`, or any other command.
- No changes to lock schema.
