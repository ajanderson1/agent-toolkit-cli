# Multi-kind catalogue — integration review for 7.0.1

AJ explicitly selected completion/inclusion of the feature and an exact 7.0.1
Release Please release. The implementation handoff was `34c9962`, including
`52947ad`; the integration base is `15132c5` in the canonical CLI repository.

This was a current-session integration review of the other workstream's code,
not a newly delegated independent subagent review. No worker fanout was used.
Review covered typed parsing/identity, guarded acquisition, admission evidence,
shared TUI refresh/Apply, native npm boundaries, checks and current documentation.

## Important findings fixed with regressions

1. **Harmless description edits invalidated mixed-age target selections.**
   Pending entries from two selections were compared as whole dataclasses, so a
   corrected description could reject an otherwise identical source selector.
   Compare subscription, key and selector instead, retaining exact source/shape
   and scope checks. The real-acquisition regression failed before the change and
   passes afterward; it also proves preparation does not create project exposure.
2. **Git Pi catalogue acquisition could register unsupported content.**
   A clone with no entrypoint, symlinked entrypoint/manifest, or unsafe declared
   path could be registered/projected. Catalogue callers now validate physical
   entrypoint packaging before registration; exact reuse validates local content
   too. Ordinary non-catalogue Pi Add behavior is unchanged. Invalid fresh clones
   remain unregistered for inspection; preexisting local edits/HEAD are retained.
   Regressions cover all four bad shapes, removed local entrypoints and valid
   declared glob entrypoints. Extension code is never imported or executed.

RED: **6 failed, 1 passed** for the review regressions, with the expected selector
error and successful invalid acquisitions proving both findings. GREEN: **49
passed** across those regressions and the typed CLI/admission/TUI cases.

## Final verification

Fresh full post-fix suite: **3,215 passed, 10 skipped in 868.47 seconds**.
Strict `make docs-build`, source compilation and whitespace checks passed.
The earlier exploratory full run was deliberately stopped before product edits;
it is not represented as a passing gate. This completed post-fix run is authoritative.
Committed-source wheel and final tagged-release artifact verification follow in
the release receipt; no development wheel is deployed to the fleet.

Secret scans of the feature history since v7.0.0 and the staged integration fixes
reported no findings. No source dependency/version/CHANGELOG bumps were authored
manually; Release Please owns the release metadata.

## Decisions

- Keep the existing small v1 parser: the approved plan permits retaining it; lack
  of an old-client compatibility requirement does not mandate rejecting old data.
- Honor AJ's requested 7.0.1 via a `Release-As` footer, not hand-edited version files.
- This code release does not admit new real assets, certify third-party quality,
  install native packages, change fleet settings or invent historical approvals.
- The separate central asset workspace is undergoing concurrent subtree cleanup.
  Its source/catalogue layout must not be restored or overwritten by CLI cleanup.
  A preserved catalogue bundle supplies a stable conversion fixture for smoke
  verification; unrelated central-workspace branches are outside CLI cleanup.
