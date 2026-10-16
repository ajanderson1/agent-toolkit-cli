---
title: Keep project collection inventory and doctor consistent after Save
date: 2026-10-16
module: skills
problem_type: logic_error
component: project-collection-inventory-and-doctor
severity: high
tags: [skills, collections, scope, doctor, preservation]
---

# Project collection Save and doctor consistency

A legacy project wrapper can legitimately become eleven project child records
with only five selected projections, while the global lock still contains the
old wrapper. Scoped conversion was correct; two read models disagreed with its
output. Inventory reused the scoped mutation marker to suppress container rows,
so retiring the project wrapper reintroduced the library wrapper as a missing
root skill. Doctor's older raw-slug membership rule called every project-only
child unlisted. Its optional library-add preview also omitted the child selector,
while acceptance used a different acquisition path.

## Repair boundaries

- Container presentation identities are separate from the scoped wrapper/backing
  that Apply may mutate. Source/ref-owned rootless Git containers may be omitted
  as plain skills, but conflicting projections and historically tracked real
  root documents must not be hidden.
- Project children are exempt from ordinary library-inclusion warnings only when
  the retained library/project legacy backings, source/ref/path, unique child
  identity and canonical target prove their derivation. Missing payloads and
  identity/ownership conflicts remain diagnostic. Neither reader writes a lock.
- Optional library registration previews and accepted actions invoke the same
  `skills add` command. `--path` selects the exact recorded directory separately
  from frontmatter name/custom slug; `--ref` retains branches, tags or SHA pins.
  Add remains library-only and has no `-g` option. Registration checks existing
  canonical ownership instead of treating existence as identity proof.
- Existing distinct global clones are retained, not deduplicated or reset.
  Their conservative physical-identity ambiguity is not a cleanup instruction.

## Regression surface

`tests/test_cli/test_project_collection_regression.py` uses disposable HOME and
real independent local Git backings, including unpublished commits and exact
index/staged/unstaged/untracked snapshots. It covers fresh-process inventory,
full doctor, post-doctor global-wrapper-plus-child shape, wrong-source/ref/path,
missing payloads, foreign targets, duplicate identities and preview/action parity.
HOME Git config denies every protocol except file; a product-Git call proves
that denial survives environment scrubbing.

`tests/test_tui/test_project_collection_apply.py` drives actual Project Apply,
explicit Refresh and a fresh app, with eleven real rows and five Standard
selections. The fixture asserts imports come from the checkout under test.
Focused checks and screenshots do not replace full-suite, strict-docs,
independent-review or real continuous-integration delivery gates.
