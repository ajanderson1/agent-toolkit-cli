# Lock schema: distinguish user pin from observed upstream tip — design

**Issue:** #345
**Tier:** standard
**Date:** 2026-06-12

## Problem

`skills-lock.json` / `.skill-lock.json` overloads two `LockEntry` fields:

- `ref` means **both** "branch/tag the user tracks" **and** (since #330) "commit
  SHA the user pinned." Every consumer that needs to tell them apart calls
  `looks_like_sha(entry.ref)`.
- `upstream_sha` means "observed upstream tip at add/update time" for every
  store-owned entry. It reads like a pin but must **never** be used as one —
  pinning on it would detach every branch-tracking entry at a stale SHA (the P1
  caught in #330's review, guarded by
  `test_doctor_reclone_branch_entry_lands_on_current_tip`).

The overload is the root cause of a class of bug: every verb that touches `ref`
inherits the `looks_like_sha` heuristic, and a verb that forgets it ships a
latent SHA bug. Today the heuristic is duplicated across **six** call sites and
is re-derived ad hoc (the inventory site, added in #386, also has to AND in an
`origin == "store-owned"` gate so an npm entry with a hex `ref` is not read as a
pin). Worse, **seven clone paths** forgot the heuristic entirely and have a live
bug: they pass a SHA `ref` straight into `git clone --branch <ref>`, which git
rejects. Only the pi-extension add/reclone paths (#330) and the two shallow
`import` paths (#259) handle a SHA today; every other clone site —
`agent add`/`skill add` (single + monorepo), `skill install`/`agent install`,
`ensure_project_canonical` (the normal project-install path), and the skill +
agent **doctor reclone** paths — is broken for SHA pins. `agent add --ref <sha>`
is the most-used SHA-pin entry point and fails today with `fatal: Remote branch
<sha> not found`.

## Decision: derived in-memory reader, no on-disk change

The lock file is the **`vercel-labs/skills` byte-compatible interop format**
(`skill_lock.py:14-16`: "never downgrade an existing file in place, because
`npx skills` reading it later would reject a mismatched version"). v1/v3 are
*their* version numbers, not ours.

Two structural options were considered:

- **A — derived reader (CHOSEN).** Decide "is this `ref` a user pin?" in **one**
  place — read-only properties on `LockEntry` plus a module helper — and repoint
  every consumer at it. **Zero on-disk change**: the lock stays byte-identical,
  so `npx skills` interop is untouched. The deep trigger (schema/migration) is
  therefore *not* tripped.

- **B — persisted `pin` field + schema version bump (REJECTED).** This is what
  the issue body floated. Rejected for the interop reason: because the format is
  one we do not own, a persisted `pin` field **cannot** let us drop `ref`
  (`npx skills` still needs `ref`), so B introduces **two sources of truth that
  must be kept in sync** — strictly worse than one field with a derived reader.
  A version bump we own would orphan the file from `npx skills` entirely. The
  derived reader is the **genuine structural ceiling for a format we don't
  own**, not a stopgap. **Decision recorded here resolves #345; it does not
  down-scope it** (confirmed by the PM, advisor-backed by data-steward + cto).

## Components

### 1. The discriminator (in `skill_lock.py`)

`looks_like_sha` moves from `pi_extension_add.py` into `skill_lock.py` (its
natural home, beside `LockEntry`) and is re-exported from `pi_extension_add` so
the existing import path still resolves. **The regex is not touched** —
behaviour-preserving only.

A module-level helper and two read-only `LockEntry` properties express the
meaning:

```python
def is_sha_pinned(entry: LockEntry) -> bool:
    """True when the entry's `ref` is a user SHA-pin: a SHA-shaped ref on a
    store-owned (git-cloned) entry. An npm entry carrying a hex `ref`
    (hand-edited / future-schema) is NOT a pin — preserves the #386
    phantom-pin fix by gating on source_type internally."""
    return entry.source_type != "npm" and looks_like_sha(entry.ref)


@dataclass
class LockEntry:
    ...
    @property
    def ref_looks_pinned(self) -> bool:
        return is_sha_pinned(self)

    @property
    def ref_tracks_branch(self) -> bool:
        """True when the entry follows a moving branch/tag (or the remote
        default when ref is None) rather than a fixed SHA — i.e. store-owned
        and not SHA-pinned. npm entries track nothing here (no clone)."""
        return self.source_type != "npm" and not looks_like_sha(self.ref)
```

Naming is deliberate: **`ref_looks_pinned`**, not `pin` — it is a *derived*
reading of the existing `ref`, never a persisted field. `upstream_sha` is
**never** consulted by either property; it remains "observed tip, never a pin."

The pinned SHA value itself is `entry.ref` (read directly) at sites that need it,
guarded by `entry.ref_looks_pinned` — there is no `entry.pin -> str | None`
accessor, because introducing one would re-imply a persisted field.

### 2. Call-site collapse (six sites, behaviour-preserving)

| Site | Before | After |
|---|---|---|
| `pi_extension_inventory.py:117` | `origin == "store-owned" and looks_like_sha(entry.ref)` | `entry.ref_looks_pinned` |
| `pi_extension_doctor.py:370` | `ref_is_sha = looks_like_sha(ref)` | `entry.ref_looks_pinned` / `entry.ref_tracks_branch` |
| `commands/pi_extension/push_cmd.py:84` | `if looks_like_sha(entry.ref)` | `if entry.ref_looks_pinned` |
| `commands/pi_extension/reset_cmd.py:77` | `if looks_like_sha(entry.ref)` | `if entry.ref_looks_pinned` |
| `commands/pi_extension/update_cmd.py:71` | `if looks_like_sha(entry.ref)` | `if entry.ref_looks_pinned` |
| `pi_extension_add.py:116` | `parsed.ref if looks_like_sha(parsed.ref) else None` | **stays** — classifies a *parsed source* before a `LockEntry` exists; calls the same `looks_like_sha` helper (now imported from `skill_lock`) |

The inventory site's `origin == "store-owned"` gate is **absorbed into the
property** (which derives npm-ness from `source_type`). The `add.py:116`
exception is legitimate: it has a `ParsedSource`, not a `LockEntry`, so it keeps
calling the bare helper.

### 3. Clone-path fix (seven sites — the live bug) via a shared helper

`skill_git.clone(url, dest, ref=ref, ...)` does `if ref: cmd += ["--branch",
ref]` (`skill_git.py:111-112`). A SHA `ref` therefore becomes `--branch <sha>`,
which git rejects. The correct strategy is the one pi-extension already uses
(`pi_extension_doctor.py:375-391`): when SHA-pinned, clone at HEAD (`ref=None`),
best-effort `fetch_ref(sha)`, then `checkout(sha)` as the fail-loud authority;
when branch-tracking, clone `--branch <ref>` (or `ref=None` → remote default,
the #332 master-vs-main case).

A shared helper **`skill_git.clone_pinned_or_branch(url, dest, *, ref, env)`**
encapsulates that dance as a verbatim extraction of the working pi-extension
code. It takes a raw `ref` (not a `LockEntry`) and re-derives the pin internally
via `looks_like_sha` — clone sites never hold an npm entry (npm = no clone), so
the bare `looks_like_sha` here is equivalent to `is_sha_pinned` at every site
that calls it; the docstring records that invariant. All clone sites passing a
user/lock `ref` straight into `--branch` route through it:

| Site | Current | In scope |
|---|---|---|
| `commands/agent/add_cmd.py:120` (`agent add`, single) | `clone(parsed.url, canonical, ref=parsed.ref)` | yes |
| `commands/agent/add_cmd.py:199` (`agent add`, monorepo parent) | `clone(parsed.url, parent_dir, ref=parsed.ref)` | yes |
| `commands/skill/__init__.py:314` (`skill add`, single) | `clone(parsed.url, library_dir, ref=parsed.ref)` | yes |
| `commands/skill/__init__.py:357` (`skill add`, monorepo parent) | `clone(parsed.url, parent_dir, ref=parsed.ref)` | yes |
| `skill_install.py:156` (skill library install) | `clone(plan.source.url, canonical, ref=plan.ref)` | yes |
| `skill_install.py:444` (`ensure_project_canonical`, project install) | `clone(source_url, project_canonical, ref=entry.ref)` | yes |
| `agent_install.py:275` (agent project install) | `clone(plan.source.url, canonical, ref=plan.ref)` | yes |
| `skill_doctor._make_reclone_action` (`skill_doctor.py:345`) | `clone(url, canonical, ref=ref)` | yes |
| `skill_doctor._make_monorepo_reclone_action` (`skill_doctor.py:387`) | `clone(entry.parent_url, parent_dir, ref=entry.ref)` | yes |
| `agent doctor `_make_readd_library_action`` (`commands/agent/doctor_cmd.py:99`) | `clone(url, canonical, ref=entry.ref)` | yes |

That is **ten** clone call sites (seven add/install + three doctor) — the spec's
"seven clone paths" in the Problem section counts the add/install group; the
three doctor paths were the originally-reported subset. All ten route through
the one helper.

> **Monorepo cache key is unchanged.** The two monorepo sites
> (`skill_doctor.py:387`, `add_cmd.py:199`, `skill/__init__.py:357`) compute
> their parent-clone cache dir via `parent_clone_path(..., ref=entry.ref)` which
> keys the dir on the raw ref (`<repo>@<sha>` vs `<repo>@<branch>`,
> `skill_paths.py:163`). That call stays exactly as-is — only the subsequent
> `clone(...)` becomes `clone_pinned_or_branch(...)`. Collapsing the cache key to
> `ref=None` would break pin isolation between two skills from the same monorepo
> at different pins.

> The misleading comment at `skill_doctor.py:327-330` ("Pass the pinned ref when
> one exists; otherwise None") describes intended behaviour the code does not
> implement — it passes `entry.ref` unconditionally. The fix makes code match
> intent and corrects the comment.

The pi-extension reclone path (`pi_extension_doctor._make_reclone_action`)
already implements this dance inline; it is only **refactored** to delegate to
`clone_pinned_or_branch`, so all paths converge on one implementation.

**Explicitly out of scope** (they already handle SHAs correctly): the two
shallow `import` clone paths `commands/agent/import_cmd.py:88` and
`commands/pi_extension/import_cmd.py:115` (#259 depth-1 clone-then-`fetch_ref`),
and `pi_extension_add.py` (#330, already clones-at-HEAD + checks out a pin).

## Blast radius

**One schema, one new git helper, ten clone call sites repointed.** `LockEntry`
lives in `skill_lock.py`; `agent_lock` and `pi_extension_lock` are re-export
facades over it; `instructions_lock` is a **separate** dataclass and is
unaffected (it has no SHA-pin concept). No on-disk format change, no migration,
no version bump. The only new public symbol is
`skill_git.clone_pinned_or_branch`; the ten clone sites change one line each (the
`clone(...)` call) and the monorepo sites keep their `parent_clone_path(ref=...)`
cache call untouched.

## Error handling

- Clone-path fix preserves the existing fail-loud contract: a failed `checkout`
  removes the partial clone and re-raises (no orphan dir, #313).
- `fetch_ref` stays best-effort (a full clone already holds ref-reachable
  objects; the fetch only rescues full-SHA pins not reachable from advertised
  tips, and always fails for abbreviated pins — checkout resolves those
  locally). Identical to the pi-extension precedent.
- The properties are pure and total: they never raise; `ref=None` → not pinned,
  tracks branch (store-owned) — exactly today's behaviour.

## Testing

- **Truth-table unit test** for `is_sha_pinned` / `ref_looks_pinned` /
  `ref_tracks_branch`, covering every row, **including the `npm` + hex-`ref`
  row** (the #386 phantom-pin regression guard): npm+hex → not pinned;
  store-owned+SHA → pinned; store-owned+branch → tracks branch; store-owned+None
  → tracks branch (default); npm+branch → neither.
- **Clone-path red-green:** a SHA-pinned skill entry and agent entry recloned
  via doctor land on the pinned commit (not rejected by `--branch <sha>`); a
  branch entry lands on the current tip (existing
  `test_doctor_reclone_branch_entry_lands_on_current_tip` must stay green). Use a
  hermetic `file://{bare}/...` source as in #330.
- **Existing suite stays green** — the six call-site collapses are
  behaviour-preserving; the full suite is the regression net.

## Out of scope

- Any on-disk lock format change, new persisted field, version bump, or
  migration (option B, explicitly rejected above).
- Touching the `looks_like_sha` regex.
- `instructions_lock` (separate dataclass, no pin concept).
- The npm/registry pin story (npm entries never carry a user SHA pin here).
- The two shallow `import` clone paths (`agent/import_cmd.py:88`,
  `pi_extension/import_cmd.py:115`) and `pi_extension_add.py` — they already
  clone-then-checkout a SHA correctly (#259 / #330). Refactoring them onto the
  shared helper is a tidy-up, not a fix, and is deferred to avoid scope creep.
