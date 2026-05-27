# Design — Shallow-clone source repos in `skill import` (#259)

**Mode:** `--auto` · **Type:** `fix` (perf) · **Date:** 2026-05-27

## Problem

`skill import` reconstructs the global library from another machine's
`skills-lock.json`. For every skill it shells out to `git clone` with **full
history, no `--depth`**. The library only ever needs the *tree* at the skill's
pinned commit — full history is pure waste.

Evidence (issue #259): re-running the 36-skill himalayas import, 35 small repos
clone in seconds each, but `pinchtab/pinchtab` (32 MB monorepo) took **~24 min**
— longer than the other 35 combined. A single fat source repo gates the run.

## Where the clone happens

`import_cmd` → `reconstruct_skill_into_library()` → one of:

- `_reconstruct_single()` (`commands/skill/__init__.py:60`) — single-repo skills
  (the pinchtab case). `clone(url, dir, ref) → checkout(pin_sha) →
  remote_head_sha(ref) → head_sha()`.
- `_reconstruct_monorepo()` (`commands/skill/__init__.py:80`) — monorepo skills.
  `clone(parent_url, parent_dir, ref)`, then symlink a subpath; pins to **parent
  HEAD** (no `pin_sha`).

Both bottom out in `skill_git.clone()` (`skill_git.py:87`), a full clone.

## Empirically-verified constraints

A `git clone --depth=1` fetches **only HEAD's tree**. Three things follow,
confirmed against real git:

1. **Checking out an older pinned SHA fails** on a depth-1 clone
   (`fatal: unable to read tree <sha>`). So `_reconstruct_single` cannot just
   shallow-clone-then-`checkout(pin_sha)` — it must first fetch that one commit:
   `git fetch --depth=1 origin <sha>` → `checkout <sha>` works.
2. **`git rev-parse origin/<ref>` still resolves** on a shallow clone (the
   remote-tracking ref points at the branch tip we cloned). So
   `remote_head_sha(ref)` keeps returning the branch HEAD unchanged.
3. The existing SHA semantics are preserved exactly: `upstream_sha` = branch tip
   (`remote_head_sha`), `local_sha` = the pinned commit (`head_sha` after
   checkout). Shallow does not change *which* SHAs get recorded, only how much
   history is transferred.

## Design

### `skill_git.clone()` — add an opt-in `depth` parameter

```python
def clone(url, dest, *, ref, env, depth: int | None = None) -> GitResult:
    cmd = ["git", "clone"]
    if depth is not None:
        cmd += ["--depth", str(depth)]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(dest)]
    ...
```

`depth=None` (default) = today's full clone — every existing caller is
byte-for-byte unchanged. The `--depth` flag is added **before** `--branch`/url,
so the GIT_TERMINAL_PROMPT / GIT_SSH_COMMAND env hardening from #251 is
untouched.

### `skill_git` — add a `fetch_ref` helper for the pin-then-checkout path

`_reconstruct_single` needs the *pinned* commit on a shallow clone before it can
check it out. Add:

```python
def fetch_ref(repo, *, ref, env, depth: int | None = None) -> GitResult:
    """Fetch a single ref/sha (optionally shallow) into `repo`."""
    cmd = ["git", "-C", str(repo), "fetch"]
    if depth is not None:
        cmd += ["--depth", str(depth)]
    cmd += ["origin", ref]
    ...
```

This is distinct from the existing `fetch()` (which does `fetch origin --prune`,
no specific ref) — keep both; they serve different callers.

### `_reconstruct_single()` — shallow path

```python
def _reconstruct_single(parsed, slug, *, pin_sha):
    library_dir = library_skill_path(slug)
    if not library_dir.exists():
        library_dir.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(parsed.url, library_dir, ref=parsed.ref, env=None,
                        depth=1)
    if pin_sha and skill_git.is_git_repo(library_dir):
        # depth-1 clone only has HEAD's tree; fetch the pinned commit first.
        skill_git.fetch_ref(library_dir, ref=pin_sha, env=None, depth=1)
        skill_git.checkout(library_dir, ref=pin_sha, env=None)
    # remote_head_sha + head_sha unchanged — both work on a shallow clone.
    ...
```

**Edge case — pinned SHA equals HEAD:** the `fetch_ref` is harmless (git is a
no-op fetch of a commit it already has) and `checkout` is a no-op. No special
casing needed.

**Edge case — `pin_sha is None` (`--latest`):** no fetch/checkout; the depth-1
clone of branch HEAD is exactly what `--latest` wants. `head_sha` =
`remote_head_sha` = branch tip.

### `_reconstruct_monorepo()` — shallow path

The parent clone pins to parent HEAD, no `pin_sha` to honour. A plain
`clone(..., depth=1)` is sufficient and correct — it lands the tree we symlink
into.

```python
skill_git.clone(parsed.url, parent_dir, ref=parsed.ref, env=None, depth=1)
```

The existing `else:` branch (parent already cloned → `fetch()`) is unchanged.

### Scope guard — only `import` goes shallow

`skill add` (`_add_single` / `_add_monorepo`) and `skill doctor`'s reclone path
also call `clone()`. They are **not** changed here: `add` clones a skill the
user intends to *work on and push from*, so full history is the right default.
This issue is specifically about `import` (cross-machine sync of pinned trees).
Because `depth` defaults to `None`, those callers keep full clones for free.

## Out of scope

- Converting a shallow library clone back to full later (e.g. if a `push` is
  attempted from an imported skill). Imported skills are pinned, read-only-ish
  copies; if a future flow needs full history it can `git fetch --unshallow`.
  Not this issue.
- `update`'s `fetch + merge` path — imported clones are shallow but `update`
  already fetches; a shallow→merge can be slow but that is a separate perf
  question and out of scope for the import speed-up.

## Test plan (TDD)

Real-git `git_sandbox` fixture (no mocks for behaviour), matching the existing
`test_skill_git.py` / `test_skill_import.py` style.

**`skill_git` unit:**

1. `clone(..., depth=1)` produces a shallow clone — `git rev-parse
   --is-shallow-repository` is `true`; full clone (default) is `false`.
2. `clone(..., depth=1)` still sets `GIT_TERMINAL_PROMPT=0` + BatchMode ssh
   (regression guard for #251 — depth must not disturb env hardening).
3. `fetch_ref(repo, ref=<old_sha>, depth=1)` makes a previously-unreachable
   commit checkout-able on a shallow clone.

**`reconstruct` / import behaviour (the real bug):**

4. Import of a single-repo skill pinned to a **non-HEAD** older SHA lands the
   library clone at exactly that SHA, with the right tree contents — this is the
   test that would FAIL against a naive `clone --depth=1 + checkout` (Test A
   above) and PASS with the fetch-pin-then-checkout design.
5. Import of a single-repo skill records the same `upstream_sha` (branch tip)
   and `local_sha` (pinned commit) the full-clone path recorded — semantics
   unchanged.
6. `--latest` import of a single repo lands branch HEAD (shallow), SHAs correct.
7. Monorepo import lands the subpath tree and pins to parent HEAD (shallow).
8. The resulting library clone is shallow (`--is-shallow-repository` true) —
   proves the perf fix actually engaged end-to-end, not just in the unit.

## Risks

- **Server must support shallow fetch of an arbitrary SHA.** GitHub does
  (`uploadpack.allowReachableSHA1InWant` / `allowAnySHA1InWant` are on for
  github.com). `file://` sandboxes do too (verified). A self-hosted remote that
  forbids SHA-in-want would break `fetch_ref` — but those hosts already break
  any SHA-pinned workflow; acceptable.
- **No behaviour change for `add`/`doctor`** because `depth` defaults to `None`.
  The only files touched are `skill_git.py` and `commands/skill/__init__.py`.
