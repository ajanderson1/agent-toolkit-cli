---
title: Preserve checkout ownership when reconciling skill collections
date: 2026-10-16
module: skills
problem_type: logic_error
component: collection-registration-and-projection
severity: high
tags: [skills, collections, preservation, rollback, textual]
---

# Preserve checkout ownership when reconciling skill collections

Issue #529 adds source/ref collection controls over existing real skill records.
A rootless repository previously recorded as one skill needs more than different
checkboxes: its containing projection must be replaced by all desired child
projections before a deselected child is actually disabled.

## Constraints and chosen approach

- Registration preflights the complete source/ref/path/target batch and reuses
  existing checkouts without advancing HEAD. Even a clean checkout can contain
  unpublished commits. Index bytes and untracked work matter too. Upstream growth
  requires an explicit merge-aware `skill update`, not an add-time hard reset.
- Collection Apply runs before ordinary per-slug project materialization. It
  derives complete sibling selection from actual exposure plus queued deltas.
  Parent presentation IDs never become installer arguments.
- Legacy backing checkouts stay at their original paths. Retain the fake wrapper
  record while another harness still uses it, but exclude it from source-install.
  After the last wrapper projection is retired, real child targets retain backing
  ownership; discovery and doctor must not classify that checkout as disposable.
- Recovery journals exact affected links and raw affected lock records. Merge
  recovery against a freshly read document and revalidate ownership at writes.
  Serializing an entire v3 lock with `write_lock` would refresh unrelated entry
  timestamps; targeted raw-record patches preserve those records and wrapper
  metadata exactly. Validate the same raw snapshot against the original affected
  expectations before it becomes the journal baseline: a later read cannot adopt
  a third party\'s changed affected value as transaction-owned. Atomic file
  replacement alone is not stale-rollback protection.
- Report recovery conflicts rather than overwrite changed links/records. A
  partially recovered preserved backing must not be replaced with a new upstream
  clone merely because normal parent-cache paths are absent.
- Internal collection rebuilds preserve pending edits. Explicit Refresh still
  clears the active queue, and a confirmed harness-settings discard clears every
  queue, preserving the existing public interaction contract without asset writes.
- A matching detached tag is verified by its peeled commit without reset;
  another checked-out branch is not adopted merely for sharing that commit.
- Real child health requires its `SKILL.md`, not only a matching directory/link.
  A locally deleted document remains missing and visible; Apply does not recreate
  it from upstream or count it as a healthy all-selected collection. Rootless
  legacy containers remain a separate, non-installable backing representation.
- Existing explicit single-child copy fallback remains supported. Recovery removes
  a newly copied snapshot only when its identity and complete content/mode snapshot
  still match; changed copies remain visible recovery conflicts. This is not a
  filtered-root conversion path for collection reconciliation.
- Git inventory uses `--no-optional-locks` so even read-time status probing does
  not refresh the operator's index. Reads, toggles, Revert, no-op Apply and
  unrelated Apply never reconcile legacy assets.

## Exposure limitation

Directory containment alone does not prove a harness discovers nested skills.
The locally inspected Pi loader stops at a genuine root `SKILL.md`; Toolkit's
inventory also recognizes nested paths. Shared-reader isolation cannot be inferred
from either rule alone. Root-on/nested-off combinations whose independence is
unproven are refused before writes, with truthful diagnostics, rather than using
filtered copies or new persisted selection flags.

## Verification surface

Disposable Git/filesystem fixtures cover complete sibling replacement, staged and
committed work, multi-harness wrapper lifetime, fresh-lock recovery, injected write
failures and recovery conflicts. Headless Textual tests cover collection controls,
all-kind pending preservation, partial failure/retry and Revert. The visual matrix
uses realistic workflow skill names at 120x40 and 180x50; capture it with:

```bash
ATK_529_VISUAL_DIR=assets/verification/529 uv run pytest -q tests/test_tui/test_skill_collection_visuals.py
```

Independent PR review and the full pytest/strict MkDocs gates remain separate
requirements; focused tests or screenshots are not substitutes.
