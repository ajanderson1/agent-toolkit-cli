# Design: fix SHA-pinned `pi-extension add`

**Issue:** #330 (repurposed from "speed up pi-extension install: shallow-clone")
**Date:** 2026-06-10
**Tier:** standard

## Background: how this issue changed

#330 was originally filed to make `pi-extension add` faster by shallow-cloning
(`--depth 1`) the source repo, mirroring `skill import` (#259 / PR #261). The
stated premise was that re-transferring the `ajanderson1/skills` monorepo's
*full history* dominates install time.

That premise was **measured and found false** (2026-06-10):

| | Full clone (today) | Shallow `--depth 1` |
|---|---|---|
| Wall time (3 runs) | 4.45 / 4.25 / 4.26 s | 4.18 / 4.18 / 4.27 s |
| `.git` size | 924 KB | 708 KB |
| History | 164 commits | 1 commit |

The full-vs-shallow delta is 0–0.27 s — within network jitter. The repo's entire
history is 924 KB; depth=1 saves ~216 KB. The ~4.2 s is dominated by the
TLS/SSH handshake and GitHub round-trips, which `--depth 1` does **not** reduce.
Separately, pi extensions install via `npm:<spec>` (registry-tracked, **no clone
at all**) far more often than via a git source, so the clone path is not even the
common one. The speed work was therefore dropped as not worth the added code.

While verifying the clone path, a **real latent bug** surfaced, which this issue
now targets.

## 1. Problem statement (Firm)

`pi-extension add` cannot install a source pinned to a commit SHA. The `add` path
passes the parsed `ref` straight into `git clone --branch <ref>`
(`pi_extension_add.py:95`), and `git clone --branch` only accepts a **branch or
tag name** — a raw commit SHA is rejected:

```
$ pi-extension add ajanderson1/skills@22d0c764cd6c10ed06a7877e55a606d3435f1ec5
fatal: Remote branch 22d0c764cd6c10ed06a7877e55a606d3435f1ec5 not found in upstream origin
```

Confirmed against the real `add()` code (2026-06-10). Branch and tag refs work;
SHA refs fail entirely. The bug is reachable from **any source shape that can
carry a SHA ref**:

- GitHub shorthand: `owner/repo@<sha>` → `parsed.ref = <sha>`
- HTTPS/`file://` URL with `/tree/<sha>/` → `parsed.ref = <sha>`

(SSH `git@host:owner/repo` and bare local paths have no ref syntax, so they
always yield `ref=None` and are unaffected.)

The sibling `pi-extension import`, `agent import`, and `skill import` paths
already solved this (#259): they never pass a SHA to `--branch`; they clone at
the default HEAD (or the branch/tag ref) and then `fetch_ref(<sha>) + checkout`
to land on the pinned commit. The `add` and doctor-reclone call sites were left
on the broken `--branch <ref>` shape.

## 2. Acceptance criteria (Firm)

1. `pi-extension add <source>@<sha>` (GitHub shorthand) succeeds and the store
   copy's `HEAD` is the pinned `<sha>`.
2. `pi-extension add https://github.com/<owner>/<repo>/tree/<sha>/` (URL form)
   succeeds and lands on `<sha>`.
3. Branch-ref and tag-ref adds continue to work exactly as before (no regression).
4. A ref-less add continues to land on the source's default branch HEAD.
5. A SHA that does not exist in the remote fails loudly (raises, no lock entry
   written — the #283 lock-honesty contract holds — **and no orphaned store
   directory left on disk**, the #313 class of bug).
6. The lock entry written for a SHA-pinned add records the pinned SHA in
   `ref` and `local_sha`; `upstream_sha` is `None` (the post-checkout
   `rev-parse origin/<sha>` has no remote ref to read and is caught — this
   differs from import-migrated entries, where `upstream_sha` carries the pin).
7. The doctor reclone action (`_make_reclone_action`) reclones an entry whose
   `ref` is SHA-looking onto that pinned commit. It must NOT treat
   `upstream_sha` as a pin: `add()` records `upstream_sha` for *every*
   store-owned entry as the observed tip at add time, so pinning on it would
   silently detach every branch-tracking entry at a stale SHA on reclone.
8. `pi-extension update` and `pi-extension reset` skip a SHA-pinned entry with
   an informational message (`pinned to <sha> — skipping (remove and re-add to
   change the pin)`, exit 0) instead of failing with a phantom merge conflict /
   reset error — without this, one pinned entry poisons every `update` run
   (`merge(origin/<sha>)` is rejected by git at `update_cmd.py:73`; the same
   wall at `reset_cmd.py:88`).
9. No change to the lock schema. The CLI surface changes only additively: a
   previously-failing input starts working, and update/reset gain the pinned
   skip message above.
10. Abbreviated SHA pins (7–39 hex) work: `git fetch origin <short-sha>` cannot
   work (fetch resolves only remote refs and full object IDs), so the fetch
   step is best-effort and `checkout` — which resolves abbreviations locally
   against the full clone — is the fail-loud authority.

## 3. Architecture / approach

### The proven pattern (adapted — see the fetch/checkout divergence below)

`pi_extension/import_cmd.py:115-122` is the reference implementation:

```python
skill_git.clone(source_url, canonical, ref=ref, env=None, depth=1)

if pin_sha and skill_git.is_git_repo(canonical):
    try:
        skill_git.fetch_ref(canonical, ref=pin_sha, env=None, depth=1)
        skill_git.checkout(canonical, ref=pin_sha, env=None)
    except skill_git.GitError:
        pass  # pin not available; stay at HEAD
```

The key insight: **`--branch` is only ever given a branch/tag, never a SHA.** A
SHA is applied *after* the clone via `fetch_ref` + `checkout`.

One deliberate divergence from the import snippet above: in `add`, the
`fetch_ref` is **best-effort** (`try/except GitError: pass`) and `checkout` is
the fail-loud authority. Two reasons: (a) abbreviated SHA pins — `git fetch
origin <short-sha>` always fails (fetch accepts only remote refs and full
object IDs), while `checkout` resolves an abbreviation locally against the
full clone; (b) on a full clone every ref-reachable object is already present,
so the fetch only rescues full-SHA pins that aren't reachable from advertised
tips (it also makes such pins work on remotes without `allowAnySHA1InWant`
when they *are* reachable). A pin that truly doesn't exist still fails loudly —
at `checkout`.

### Applying it to `add`

The complication unique to `add` (vs `import`): `import` reads a *lock entry*
that already separates `entry.ref` (branch/tag) from `entry.upstream_sha`
(pinned commit). `add` parses a *source string* where `parsed.ref` is a single
field that may be a branch, a tag, **or** a SHA — undistinguished by the parser.

So `add` must decide, at the clone site, whether `parsed.ref` is a SHA:

- **SHA** → clone at default HEAD (`ref=None` to `--branch`), then
  `fetch_ref(parsed.ref) + checkout`.
- **branch / tag / None** → today's behaviour: `clone(ref=parsed.ref)`.

**SHA detection.** A ref is treated as a SHA when it matches `^[0-9a-f]{7,40}$`
(hex, 7–40 chars — git's abbreviated-to-full SHA range). This is the same
heuristic git itself can't avoid; a 40-hex *branch name* is pathological and not
supported by `--branch` anyway, so misclassifying it as a SHA is strictly more
correct than today. A short ambiguous string (e.g. a tag literally named
`abc123`) that is also valid hex will be treated as a SHA: `fetch_ref` of a tag
name still works (git resolves it), and `checkout` lands on it — so the
heuristic is safe in both directions. This reasoning is captured in a code
comment.

A small **public** helper keeps the call site readable (public because the
doctor module — and the update/reset commands per criterion 8 — import it):

```python
def looks_like_sha(ref: str | None) -> bool:
    return bool(ref) and re.fullmatch(r"[0-9a-f]{7,40}", ref) is not None
```

### Should we shallow-clone too?

The fix makes shallow-cloning *fall out for free* (the import pattern already
passes `depth=1`). But the measurements show no benefit, and `add`'s post-clone
`remote_head_sha`/`head_sha` bookkeeping must keep working on a shallow clone.
**Decision: do NOT add `depth=1` to `add`.** Keep the full clone; apply only the
SHA-handling fix. Rationale: the speedup is within noise, a full clone keeps the
post-clone SHA bookkeeping trivially correct, and a smaller diff is lower-risk
for install machinery (which has a repeated history of silently-broken ships in
this repo). The `fetch_ref`/`checkout` SHA steps work identically on a full
clone — `fetch_ref` of a SHA git already has is a cheap no-op.

> If the monorepo history ever grows large enough to matter, shallow-cloning can
> be revisited as a separate, measured change. Noted, not done.

## 4. Components touched

| File | Change |
|---|---|
| `src/agent_toolkit_cli/pi_extension_add.py` | At the clone site (`:95`): branch on `looks_like_sha(parsed.ref)`. SHA → clone HEAD, best-effort `fetch_ref`, fail-loud `checkout`; else unchanged. Add public `looks_like_sha` helper + `import re`. |
| `src/agent_toolkit_cli/pi_extension_doctor.py` | `_make_reclone_action` (`:337`): pin ONLY when the entry's `ref` is SHA-looking (`pin_sha = ref if looks_like_sha(ref) else None`) — never from `upstream_sha`, which is the observed tip for every add-created entry, not a pin (criterion 7). |
| `src/agent_toolkit_cli/commands/pi_extension/update_cmd.py` | Skip SHA-pinned entries with the informational message (criterion 8), before the `resolve_ref`/`merge` path. |
| `src/agent_toolkit_cli/commands/pi_extension/reset_cmd.py` | Same pinned skip (criterion 8), before the `resolve_ref`/`reset_hard` path. |
| `tests/test_cli/test_pi_extension_add.py` | New tests: SHA add lands on pin (full + abbreviated); branch/tag/ref-less still work; bad SHA fails + no lock entry + no orphan dir; `looks_like_sha` unit table. |
| `tests/test_cli/test_cli_pi_extension_lifecycle.py` (§ Task B5) | Doctor reclone of a SHA-pinned entry lands on the pin; branch-entry-with-stale-`upstream_sha` reclones onto the CURRENT branch tip (regression for criterion 7); update/reset pinned-skip tests. |

No change to `skill_git.py` (all needed primitives — `clone`, `fetch_ref`,
`checkout`, `is_git_repo` — already exist) and **no change to the lock schema**.

## 5. Data flow

```
add(source="owner/repo@<sha>")
  → parse_source        → ParsedSource(ref="<sha>")
  → looks_like_sha(ref) == True
      → clone(url, canonical, ref=None)          # default HEAD, --branch unused
      → fetch_ref(canonical, ref="<sha>")        # best-effort (rescues full-SHA wants)
      → checkout(canonical, ref="<sha>")         # fail-loud authority; resolves
                                                 # abbreviations locally
  → is_git_repo? → remote_head_sha / head_sha     # unchanged bookkeeping
                                                  # (upstream_sha lands None: no
                                                  # origin/<sha> remote ref)
  → write_lock(LockEntry(ref="<sha>", local_sha=<sha>, upstream_sha=None, ...))
```

For branch/tag/None the left branch is unchanged from today.

## 6. Error handling

- The fetch/checkout split (criterion 10): `fetch_ref` failures are swallowed
  (`except GitError: pass`) — a full clone already holds every ref-reachable
  object, so the fetch only rescues full-SHA pins not reachable from advertised
  tips, and it always fails for abbreviated pins. **`checkout` is the fail-loud
  authority**: a pin that doesn't exist in the clone raises there. Unlike
  `import` (which swallows pin failures and stays at HEAD across a *batch*),
  `add` is a single explicit user action with an explicit pin — silently
  landing on the wrong commit would violate fail-loud. So the `checkout`
  `GitError` propagates (non-zero exit), and the existing lock-after-clone
  ordering guarantees **no lock entry is written** for the failed add (#283).

  **New failure mode requiring explicit cleanup.** Today `add` has no
  cleanup block: the `clone()` at `:95` either succeeds or raises, and git
  removes the dest dir itself on a failed *clone*. But the new SHA path runs
  `fetch_ref`/`checkout` **after** a successful clone, so a failed `checkout`
  leaves a populated `canonical` directory on disk with no lock entry —
  exactly the orphaned-canonical class of bug (#313). The fix MUST therefore
  wrap the `checkout` so that on `GitError` it `shutil.rmtree`s `canonical`
  before re-raising, mirroring the import path's
  `if canonical.exists(): shutil.rmtree(...)` cleanup. A test asserts the
  directory is gone after a failed SHA add.

- Update/reset on a pinned entry (criterion 8): skip with the informational
  message and `continue`, exit 0 — not an error. A pinned entry is healthy;
  the user opted out of tracking. The message names the remedy
  (`remove and re-add to change the pin`).

  > This is a deliberate divergence from `import`'s `except GitError: pass`.
  > `import` is a best-effort batch refresh; `add` is a single deliberate pin.
  > The divergence is documented in a code comment at the `add` call site.

- Branch/tag clone failures behave exactly as today (propagate as `GitError`).

## 7. Test surface

- **`add` SHA happy path** — local bare repo with ≥2 commits; add a
  `/tree/<first-sha>` source; assert store `HEAD == first-sha` and the
  worktree content matches the pinned commit (not HEAD).
- **`add` abbreviated SHA** — same shape with a 7-char pin; assert HEAD
  expands to the full pinned commit (exercises the best-effort-fetch /
  checkout-authority split, criterion 10).
- **`add` branch/tag/ref-less regression** — existing tests stay green; add an
  explicit branch-ref add asserting it still lands on the branch tip.
- **`add` bad SHA** — a 40-hex SHA absent from the remote raises, writes **no**
  lock entry, **and leaves no `canonical` directory behind** (extends the
  existing `test_add_lock_written_only_after_clone` shape; adds the orphan-dir
  assertion).
- **`looks_like_sha` unit** — table test: full SHA, abbreviated SHA, `main`,
  `v1.2.3`, `None`, a 40-hex string → classified correctly.
- **doctor reclone SHA pin** — a lock entry with a SHA-looking `ref` reclones
  onto that commit.
- **doctor reclone branch regression** — a branch entry whose `upstream_sha`
  is one commit behind the pushed tip reclones onto the CURRENT tip, on the
  branch (guards criterion 7's no-repin rule).
- **update/reset pinned skip** — `pi-extension update` and `reset` over a
  SHA-pinned entry exit 0 and print the pinned skip message (criterion 8).

All hermetic (local bare repos via the existing `git_sandbox` fixture or an
inline one). No network. Run via `uv run pytest`.

## 8. Out of scope

- Shallow-cloning `add` (measured: no benefit; revisit only if history grows).
- The SSH/local "ref silently dropped" observation — those forms have **no ref
  syntax**, so there is nothing to fix; not a bug.
- Any change to `import`, `agent`, or `skill` paths (already correct).
- The `@<ref>/<subpath>` shorthand ambiguity (already handled by the parser with
  an explicit error).
- `pi-extension push`/`status` behaviour on a pinned entry (a pinned store in
  detached HEAD has nothing meaningful to push; documented limitation, audit
  separately if it bites).
- A first-class lock distinction between "user pin" and "observed upstream
  tip" (the `ref`/`upstream_sha` overload is the root cause of the doctor
  re-pin trap; needs a schema change — recorded as a deferred question on
  #330).

## 9. Approvals front-loaded

- **Drop the speed work / repurpose #330 to the SHA bug** — approved by AJ
  (2026-06-10), on the strength of the clone-timing measurements above.
- **Do not shallow-clone `add`** — design decision, recorded in §3; revisit only
  on measured need.
