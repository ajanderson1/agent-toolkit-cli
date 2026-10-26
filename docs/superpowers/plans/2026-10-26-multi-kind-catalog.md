# Multi-kind catalogue implementation plan

Approved direction: `../specs/2026-10-25-multi-kind-catalog-design.md`, including
AJ's requirement for admission inspection and no older-client rollout work.
Implementation base: `15132c5d6785a35c152cb1749a4b7bd48341ff36` (7.0.0 code).
CLI worktree: `.worktrees/feat-multi-kind-catalog`, branch `feat/multi-kind-catalog`.
Catalogue source: `/Users/ajanderson/GitHub/agent-toolkit/catalog` (separate Git repo).
No publishing, fleet changes, live library/settings edits or release bump.

The installed Superpowers skill files were removed by the environment reset;
`writing-plans/SKILL.md` is unavailable. Follow the same bounded plan → failing
regression tests → implementation → verification sequence inline. No worker
fanout is authorized or needed.

## Tasks

1. [x] Add failing mixed-manifest/CLI tests, then typed catalogue entries with a
   shared snapshot. Keep the existing skills API as a thin filtered view, retaining
   the small existing version-1 parser rather than rewriting every skills fixture.
   Version 2 is the new shared format; old-client support is not a requirement.
2. [x] Add shared subscription/list utilities and per-kind Git acquisition commands.
   Test exact source/ref/path/content reuse, conflicts, non-advancing agent parent
   reuse, root-only Git Pi, scope/target preflight, native npm boundary and explicit
   confirmed installation. Use real per-kind lock and native engines.
3. [x] Extend Git revision checks to agents/commands/Git Pi with separate backing
   identities and explicit native guidance; retain skills check contracts.
4. [x] Share one asynchronous catalogue snapshot across four grids; join metadata
   without adopting local content. Queue Git acquisition for Apply, revalidate the
   subscription/selected identities once per batch, preserve failed intent and
   existing cross-kind/native pending safeguards. Npm catalogue-only rows stay
   read-only with native-install guidance.
5. [x] Add an explicit local catalogue validation/admission workflow: deterministic
   source-fit checks and review evidence for new/changed entries, without executing
   upstream code or claiming automated quality approval. Record exactly what was
   checked; human/agent content-quality and representative-use review is mandatory
   before publishing. Do not invent approvals for existing entries.
6. [x] Update current CLI/TUI/asset docs and the separate catalogue guide; preserve
   every existing key/source/path/ref if converting its manifest to version 2. No
   new upstream assets are silently admitted merely to demonstrate the feature.
7. [ ] Run focused CLI/TUI regressions, full pytest, strict docs, wheel build and
   disposable installed-artifact smoke checks. Record commit/artifact identity;
   inspect final diffs and leave a clear local handoff without pushing or deploying.

## Validation

Use disposable homes/configuration/Git remotes and native mocks/fixtures only.
Existing skill collection, dirty-state, pinned-reset and native Pi behavior must
remain intact. New tests must exercise failures before product changes and cover
catalogue unavailability, stale selection, ambiguity and partial success.

Admission inspection and local acquisition safety are distinct: reviewed upstream
content never authorizes overwriting, advancing or adopting an existing local
backing. Catalogue entry removal leaves acquired library content/exposure intact.

## Verification so far

- Focused pre-change skills baseline: 55 passed.
- New parser/acquisition/TUI/check/admission tests were observed failing before
  implementation, then passing. Focused integrated run: 131 passed.
- Final full-suite coverage in two independent partitions (separate caches):
  CLI: 2,142 passed / 10 skipped; remaining tests: 1,066 passed. Total: 3,208 passed.
- The first serial run hit its 20-minute limit at 94%; its three failures were
  reproduced and fixed before the complete partitioned rerun. No pytest remained.
- Strict `make docs-build`, source compilation and whitespace checks passed.
- Catalogue conversion: 109 original entries preserved byte-for-byte at the field
  level (excluding added kind/sourceType); admission against the accepted v1 base
  reports zero new/changed selectors. No historical quality approvals were invented.
- Publication gate requires full reviewed Git commit pins; one version is selected
  per npm package identity, avoiding ambiguous duplicate native inventory rows.
- Wheel/source identity and installed-artifact smoke are the remaining check.
