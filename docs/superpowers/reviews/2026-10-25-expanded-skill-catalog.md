# Expanded skill catalogue collections — verification and review

## Delivery

Implemented locally on `feat/catalog-collections`, based on canonical GitHub commit
`74a41448cab89586fc4b048bd4d423da455e61a1` (6.1.0). No merge, release, live
installation, hosted-catalogue edit or live skill activation was performed.
The original checkout's separate multi-kind proposal and uncommitted files, and
the older demo worktree, were preserved.

Advertised and acquired children share expandable repository/ref collections.
Child matching uses normalized Git URL/ref/path, not names. Pending identities
and observed membership are frozen; only selected missing children are acquired.
One fresh catalogue snapshot validates Apply, separately from inventory refresh.
Acquisition failure blocks exposure changes for the affected collection/scope;
projection changes across requested harnesses use the ownership-checked journal.
Safely acquired library content remains, failed intents remain queued, and
unrelated units may succeed. Git checks and Info no longer require catalogue
association. Existing selectors, local work, private backing and legacy containers
are preserved.

## Evidence

All tests used disposable HOME/config/assets and local Git remotes.

| Gate | Result |
| --- | --- |
| Clean baseline | 3101 passed, 10 skipped in 442.11s |
| Task 1 focused gate | 21 passed; grouping/identity tests witnessed RED first |
| Task 2 focused gate | 15 passed; pending metadata tests witnessed RED first |
| Task 3 focused gate | 40 passed; batch/failure tests witnessed RED first |
| Task 4 combined check/collection gate | 42 passed; non-catalogue check/Info cases witnessed RED first |
| Whole-review fix/recovery gate | 38 passed, including the three reproduced review regressions |
| Full post-fix runtime suite | **3135 passed, 10 skipped in 452.60s**, code commit `cea677c6fa73c3cdbfe4a679357e550e576c9ff2` |
| Strict documentation | `make docs-build` passed |
| Package | `uv build`, wheel/sdist structure/version checks passed |
| Disposable installed wheel | CLI version/help/packaged instructions and TUI version/headless Textual pilot passed |
| Whitespace | `git diff --check` passed |

The first validated development wheel was built from code commit
`cea677c6fa73c3cdbfe4a679357e550e576c9ff2`, SHA-256
`97b262931ebeb7d8cfaf3ff5a19f740fde9d12574f2d402777312741d172879a`.
The final documentation-only closeout is rebuilt separately; its exact source
commit and wheel hash are recorded in `dist/catalog-collections-verification.json`.
This remains an **unreleased branch artifact** at the existing package version,
not the official 6.1.0 release or an installed replacement. Runtime source/tests
must remain identical to the full-suite commit for the documentation-only closeout.

## Independent whole-branch review

One fresh read-only reviewer used `openai-codex/gpt-6.1-sol:high`, run
`1e5274d5-6dcd-484d-9140-95cfeb63fa2e`, and reviewed committed range
`74a4144..9d5f24f`. The initial verdict blocked integration on two Important issues.
Both were independently confirmed by supervisor-run disposable regression probes
before product fixes (`3 failed`):

1. A legacy flat-root registration could be left outside its newly acquired nested
   sibling's transaction, allowing partial activation. Fixed by grouping operation
   ownership by normalized Git identity and journaling the actual preserved
   canonicals together, without advancing or moving their different checkouts.
   The regression injects a root unlink failure after the nested projection exists,
   verifies rollback and unchanged root, then verifies a successful retry.
2. Retained materialised singleton content was incorrectly sent through shared-parent
   inference and could no longer enable/disable. Fixed by the same preserved-canonical
   projection journal, retaining files and records rather than inventing a parent.
   Both enable and disable regressions preserve local content.

Corrective commit: `cea677c`. Both findings were fixed in one pass with RED→GREEN
regressions and a green full suite; no second reviewer was launched. The reviewer
reported no cosmetic/minor findings.

## Rulings made, in execution order

1. Added a defaulted configured-ref field to the internal `CatalogSnapshot`, since
   subscription-ref validation cannot be reconstructed from revision or child refs;
   positional compatibility is preserved. **Cost if wrong:** internal metadata
   compatibility; catalogue regression tests cover existing constructors/behavior.
2. Froze observed sibling identities in pending intent, not just the selected child,
   so local-only real-root toggles retain known nested-isolation guards offline.
   **Cost if wrong:** conservative root refusal until explicit Revert/refresh/reselect.
3. Integrated Revert coverage into the parent-selection test rather than duplicating
   its fixture. **Cost if wrong:** less isolated failure naming, no runtime difference.
4. Final suite/docs/build remained the parent's responsibility when the reviewer
   declined to judge those outcomes. They were required and executed, not waived.
   **Cost if wrong:** unverified regression risk; the gates above provide evidence.
5. Active-consumer deletion policy and the pre-existing flat-root FULL_SHA Add bug
   remained outside this diff. The supported explicit `--path .` SHA acquisition
   route is tested. **Cost if wrong:** those existing limitations remain and are
   not claimed repaired. Current reference docs warn about deleting shared backing.
6. No second independent review of post-HEAD fixes, following the authorized single
   whole-branch review. **Cost if wrong:** author regression/full-suite verification
   is the final fix gate rather than another fresh reviewer.

## Deferred and unchanged limitations

- Library Remove can still break active project links: disable consumers before
  deleting shared content. This work does not redesign deletion policy.
- Ordinary flat-root `skills add URL --ref FULL_SHA` has an existing `origin/SHA`
  lookup failure; explicit `--path .` uses the supported pinned registration path.
- The previously observed asynchronous catalogue header-count refresh issue is not
  a lifecycle fix in this increment; collection controls/count data are derived
  from real rows. No new header-refresh behavior is claimed.
- No multi-kind, source-adoption, automatic update, upstream subtree analysis or
  automatic upstream-check workflow is introduced.
