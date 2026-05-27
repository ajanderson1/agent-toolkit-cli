# Plan — Shallow-clone import (#259)

Spec: `docs/superpowers/specs/2026-05-27-shallow-clone-import-design.md`.
Scope (approved): import-only; `add`/`doctor` keep full clones via `depth=None`
default. TDD throughout — red test before each code change.

## Task 1 — `clone(depth=)` parameter (skill_git)

- **Red:** `test_clone_depth_makes_shallow_repo` — `clone(..., depth=1)` →
  `git rev-parse --is-shallow-repository` is `true`; default clone is `false`.
- **Red:** `test_clone_depth_preserves_prompt_and_ssh_hardening` — depth=1 clone
  still sets `GIT_TERMINAL_PROMPT=0` + BatchMode ssh (#251 regression guard).
- **Green:** add `depth: int | None = None` to `clone()`, inject `--depth <n>`
  before `--branch`/url. Default path unchanged.

## Task 2 — `fetch_ref()` helper (skill_git)

- **Red:** `test_fetch_ref_makes_old_sha_checkoutable` — depth-1 clone; checkout
  of an older SHA fails; after `fetch_ref(ref=old_sha, depth=1)` the checkout
  succeeds and HEAD == old_sha.
- **Green:** add `fetch_ref(repo, *, ref, env, depth=None)` doing
  `git -C <repo> fetch [--depth n] origin <ref>`, through `_run` (env scrub).

## Task 3 — `_reconstruct_single` shallow path

- **Red:** `test_import_single_pinned_old_sha_lands_exact_tree` — import a
  single-repo skill whose lock pins a **non-HEAD** older SHA; library clone HEAD
  == that SHA and tree contents match that commit. (Fails with naive
  clone+checkout.)
- **Red:** `test_import_single_records_unchanged_shas` — `upstream_sha` = branch
  tip, `local_sha` = pinned commit (semantics preserved).
- **Red:** `test_import_single_is_shallow` — resulting library clone is shallow.
- **Green:** `clone(..., depth=1)`; if `pin_sha`, `fetch_ref(pin_sha, depth=1)`
  then `checkout(pin_sha)`.

## Task 4 — `--latest` and monorepo shallow paths

- **Red:** `test_import_latest_lands_branch_head_shallow` — `--latest` single
  import → branch HEAD, shallow, SHAs correct.
- **Red:** `test_import_monorepo_shallow_parent` — monorepo import lands subpath
  tree, parent clone shallow, pins parent HEAD.
- **Green:** `_reconstruct_monorepo` first-clone uses `depth=1`.

## Verify

- `uv run pytest -q` green (pre-flight CI).
- New tests fail before each Green step (TDD discipline confirmed in flow.log).
