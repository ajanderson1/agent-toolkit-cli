# PR #518 — independent read-only static audit

## Final verdict: PASS — v5.10.0 published and verified

**Final candidate HEAD `9938f6a098d332bb437798a74d5f7d5c9525df5a`; base `dae729cfd632fca2ab00744e31953c7fd6f00d04`.** No blocking static finding remains for this candidate after #523 and corrected #524 merged. Informational final review: https://github.com/ajanderson1/agent-toolkit-cli/pull/518#issuecomment-6214298658 . Candidate remote CI and p7 confined QA subsequently succeeded (see observations below). Integrator merged as `516d1a30508a3745dabd6b610eefcdea70817ece`, whose tree is identical to the audited candidate. Release tag resolves to that commit; notes-only release currently exists without uploaded assets. Guarded dispatch, independent public asset hash/provenance verification, and pB public-download CLI/TUI runtime QA subsequently passed (see final observations below). Reviewer has not merged, dispatched, installed or published. Earlier HOLD findings below are retained as dated phase evidence, not silently reasserted against the corrected code.

Snapshot: 2026-10-16. Initial main/worktree HEAD `8ad3e9d8ee8ff219e485615016e4e827f0b06e7d`; initial release PR HEAD `4f8f40103524803d1ca5243dbe5e1d8dee63a2a9`. During review #515 merged through #522, main became `12636bdf321b1a9697ef0d1f4a589f3d71e5ddee`, and release-please regenerated #518 as **`676a09c2a4dcba684e42469fced7a2ee2132c06e`**, whose parent is exactly that main SHA. This is an intermediate exact-HEAD audit, **not** the final post-docs-fix audit.

Only this report is authored. No suite, packaging build, candidate smoke test, merge, tag, dispatch, approval, or publication was performed by this reviewer. Static inspections, Git/GitHub reads and Python syntax compilation only. The compilation may produce ignored bytecode within this worktree; no source edits.

## Findings

### P1 — Bot-created release cannot trigger artifact workflow

- `.github/workflows/release-please.yml:15-18` uses release-please with no `token` override; the action defaults to `GITHUB_TOKEN`.
- `.github/workflows/release.yml:3-5` accepts only tag pushes. No `workflow_dispatch`, `workflow_call`, or release-please downstream build step exists.
- GitHub suppresses push/release-triggered workflows from default-token operations. Therefore merging #518 can create the tag/notes but **does not provide a working artifact-upload trigger**. Switching to a `release: published` event alone would not fix token suppression.
- Official references: https://github.com/googleapis/release-please-action#github-credentials and https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow . `workflow_dispatch` and `repository_dispatch` are exceptions to suppression.
- API confirms release workflow is active, but its only observed recent listed run is old `v2.3.0` run `26251091323`; this does not validate the new path.

**Owner recommendation, not implemented:** add narrow manual dispatch support on main, selecting a required release tag plus immutable expected commit SHA. Resolve the tag and refuse any mismatch, checkout the exact commit, retain full tests/build/CLI+TUI smoke checks/version guards and exact upload checks, and explicitly upload to the selected tag (dispatching main must not accidentally use `main` as the release tag). `gh workflow run release.yml --ref <existing-tag> ...` is supported only after dispatch support exists on default branch and at the selected workflow ref. Do not delete/re-push immutable tags to simulate an event. An already-authenticated App/PAT-backed publication route is another supported option but must be explicitly selected, not assumed or introduced by this reviewer.

### P1 — No refusal on missing/stale/failed required CI

- Release-please runs on every main push and has no dependency on tests/docs or exact-SHA CI evidence; it can create release notes/tag independently of their result.
- Artifact workflow runs fresh `uv run pytest -q` at the checked-out tag and ordinary step failure blocks its later upload. **This is a useful gate, not a prior-CI guard.** It never queries test/docs workflow results for the selected SHA, verifies main ancestry, or refuses missing/stale prior evidence.
- #518 at `676a09c...` has `statusCheckRollup: []`; this is **not green**. Parent `12636bd...` test run `38886900101` succeeded, but docs run `38886899995` failed. Parent success cannot be relabeled exact candidate success.
- Do not use a rerun of an older successful SHA, `--no-verify`, forced status, skip-test switch, or post-merge publication as candidate validation.

**Safe explicit candidate-test route for owner:** after docs fix and final regeneration, run normal tests against the immutable final release candidate under the sole full-suite slot. A human/App-authenticated mirror branch pointing at the exact final commit can open a validation PR and trigger the existing `pull_request` test workflow; record whether GitHub tested the head SHA or a synthetic merge SHA and verify its tree. Alternatively add a read-only validation `workflow_dispatch` accepting and checking the immutable candidate SHA; run the existing full test gate, strict docs, and candidate build/CLI+TUI smoke verification with publication disabled. Neither route currently exists automatically for the bot branch. Keep its missing checks explicit until actual evidence exists. Reviewer does not consume the full-suite slot.

### P1 — Strict docs gate currently failed (p5 owns fix)

Run https://github.com/ajanderson1/agent-toolkit-cli/actions/runs/38886899995 at `12636bd...`, step `Run uv run mkdocs build --strict`, timestamp `2026-10-16T10:23:36.1927188Z`:

```text
WARNING -  The following pages exist in the docs directory, but are not included in the "nav" configuration:
  - plans/2026-09-10-ensure-assets-visible.md
  - plans/2026-10-15-pytest-user-state-isolation.md
  - plans/2026-10-16-499-global-instructions.md
  - plans/2026-10-16-516-collapse-command-aliases-in-help.md
  - specs/2026-09-10-ensure-assets-visible.md
  - specs/2026-10-15-pytest-user-state-isolation.md
  - specs/2026-10-16-499-global-instructions.md
  - specs/2026-10-16-516-collapse-command-aliases-in-help.md
Aborted with 1 warnings in strict mode!
```

Config anchor: `mkdocs.yml:10` (`omitted_files: warn`), with `strict: true` at line 7; exclusion block starts at line 21 and omits `plans/` and `specs/`. No individual Markdown content line is cited by this diagnostic: these are file-level omitted-nav warnings. Contrary to an INFO-only diagnosis, this exact run labels the aggregate **WARNING**. The Material banner, uv cache annotation and Node deprecation annotations are separate and are not this strict failure. Narrow owner fix should preserve strict validation, not suppress all warnings. Evidence sent directly to `atk-issues` p5 and `atk-prs` p6 via Herdr; reviewer does not edit config.

### P2 — Receipt/checksum verification is not strict provenance verification

`scripts/build_and_verify_release.py:431-476` checks wheel/sdist SHA-256 and byte counts and requires receipt/sums files to exist. It does **not** compare receipt `release`, `version`, `commit`, artifact `name` fields, timestamp, or smoke results to expected candidate identity. `get_git_commit` at 366-380 trusts `GITHUB_SHA` before actual checkout identity. For a future dispatch checking out a different SHA, blindly preserving this behavior could record the workflow commit instead of the artifact source commit.

Checksum checks at 473/475 use substring membership, not an exact parsed two-entry checksum manifest. Extra/duplicate lines or a correct expected substring embedded in a longer malformed line are not refused. Receipt metadata tampering with unchanged archive hashes is not refused. Main generation writes new metadata immediately before verifying, limiting normal fresh-run exposure, but this is **not** proof of strict stale/tampered receipt rejection. `--skip-build` selects existing archives and later overwrites old receipt/sums instead of validating their incoming provenance.

Required for a strict external/final receipt check: bind expected tag/version/actual resolved commit and exact artifact names, validate successful smoke fields, require exact checksum entries, recompute downloaded byte counts/hashes, and compare them with the receipt. Do not claim current helper enforces those absent comparisons.

### P2 — Exact upload list passes; directory-wide strict allowlist is narrower than requested

- `select_and_verify_artifacts:85-114` requires exact `agent_toolkit-<version>-py3-none-any.whl` and `agent_toolkit-<version>.tar.gz`; rejects other top-level `*.whl`, `*.tar.gz`, `*.zip`; missing expected archives fail.
- `build_artifacts:117-148` refuses any preexisting wheel/sdist before fresh build. Stale same-version archives therefore fail in the normal build path.
- It does **not** reject arbitrary extra files, other suffixes, nested files or symlinks as a strict complete directory allowlist would. Treat the guarantee as archive selection + upload allowlist, not all-directory refusal.
- `main:536-542` writes four verified paths to `release-artifacts.txt`; workflow upload at `release.yml:32-37` independently uses exactly those four step outputs, no wildcard, `fail_on_unmatched_files: true`. The allowlist text itself is not read by upload and is not uploaded. Other dist files are ignored, not shipped.
- Byte-tampered archives relative to an existing unchanged receipt are caught by hash verification. Wheel metadata version and sdist embedded version/source SHA are not directly validated by `verify_artifacts`; filenames and wheel version smoke tests provide narrower checks. No independent sdist installation is performed.

### P2 — Permissions/action pinning hardening

`release.yml:8` grants `contents: write` to the entire job, including checkout/dependency install/tests; no secrets for PyPI or `id-token` access are requested. Release-please additionally requires `pull-requests: write`. The latter's third-party action is a mutable `@v5` at `release-please.yml:15`, unlike the SHA-pinned setup-uv and upload actions in release.yml. `checkout@v4` is first-party and conforms to the first-party-major convention. A write-only upload stage/read-only verification stage would reduce exposure. No concurrency/timeout guard is declared for duplicate release runs.

## Version and campaign representation — PASS at 676a09c only

Exact PR diff changes only `.release-please-manifest.json`, `CHANGELOG.md`, and `pyproject.toml` (18 additions, 2 deletions). Manifest root `.` and project version are both **5.10.0**, not 5.9.2. Main remaining 5.9.1 before the release merge is expected. `release-please-config.json` selects root Python package `agent-toolkit`, `include-component-in-tag: false`, `include-v-in-tag: true`, no stale `release-as` override. Minor release follows new feature commits.

| Campaign issue | Merged implementation / SHA | 5.10.0 changelog representation |
|---|---|---|
| #513 isolation | #514 / `7bbc30a4938e6698fdaa49f875bfbf0e99998a6e` | tests real-library pollution fix; PR body closes #513 |
| #516 aliases | #520 / `28dc3536eee9346d85b101c3e2eb10085275efbb` | CLI collapsed aliases; explicit #516 and #520 |
| #499 global instructions | #521 / `8ad3e9d8ee8ff219e485615016e4e827f0b06e7d` | instructions global native-reader pointers; PR body closes #499 |
| #515 inventory/import | #522 / `12636bdf321b1a9697ef0d1f4a589f3d71e5ddee` | inventory untracked assets/safe repair; PR body closes #515 |

All four commits are ancestors of the exact candidate. #519 release packaging and #517 TUI display are also listed. Omission of literal issue #513/#499/#515 identifiers is not an omitted feature: entries link their actual merged implementation PRs. Final docs/workflow fix must be included in a new regenerated release candidate and re-audited; this candidate does not contain it.

## Coordination update

Parent assigned pB (`atk-release-build`) a narrow guarded-dispatch fix in a separate owned worktree based on `12636bd...`; reviewer will inspect the actual PR and exact HEAD when live, not implement it. p5 owns the docs fix and sole local full-suite slot.

A concrete candidate test run now exists: https://github.com/ajanderson1/agent-toolkit-cli/actions/runs/38886937763 , attempt **2**, `event: pull_request`, workflow `test`, API `headSha: 676a09c2a4dcba684e42469fced7a2ee2132c06e`. It completed **successfully**, with `2448 passed, 5 skipped in 155.47s` at `10:38:42Z`. Checkout log explicitly uses `refs/remotes/pull/518/merge`, synthetic merge `d186487` merging `676a09c...` into `12636bd...`. This is real intermediate candidate integration evidence, not direct-head execution. Thus a legitimate rerun route exists for this candidate; no mirror/validation-dispatch workaround is necessary if a real run for the **final regenerated** HEAD can similarly be rerun and its checkout identity verified. It cannot be transferred to a newer HEAD. Prior empty-rollup observation describes the initial snapshot only.

### Docs dependency #523 — static review

PR https://github.com/ajanderson1/agent-toolkit-cli/pull/523 exact HEAD `9278209af6f158216bf3e52f324b5239bb6e7387`, base `12636bdf321b1a9697ef0d1f4a589f3d71e5ddee`: only adds `specs/`, `plans/`, and `reviews/` to `mkdocs.yml` exclusions. `strict: true` and omitted-files warning remain unchanged. **No static finding on this narrow fix.** Owner reports strict MkDocs and normal pre-push passed (2448/5); reviewer independently inspected diff, not rerun commands. Remote pytest run `38888591595` subsequently completed SUCCESS at that exact HEAD. Parent reports pC independent review followed by merge as **`3794b97f95b7337cb39fc40f0015435980afade4`**; reviewer independently verified the merge and main docs run **`38889003268` SUCCESS**. pB must incorporate that base before its next gate. #518 regenerated to intermediate `0318f0398e1a5f31551a56b8fe43f0cc9805c20b` on this base; no final approval issued. Reviewer's durable report tree is deliberately excluded from future published docs by this fix.

## Guarded-dispatch dependency #524 — HOLD at first reviewed HEAD

Exact HEAD **`15f8295b717164d0dfdddcf1463690b80a93d9d6`**, base **`3794b97f95b7337cb39fc40f0015435980afade4`**, inspected in the newly assigned clean `review-524-guarded-dispatch-20261016` worktree without writes there. Durable informational review: https://github.com/ajanderson1/agent-toolkit-cli/pull/524#issuecomment-6214079878 .

Two P1 blockers remain:

1. `release.yml:87-96`: upload has no `tag_name` bound to validated target. Pinned softprops `main.ts` rejects a branch dispatch without explicit tag (`GitHub Releases requires a tag`); dispatching a different tag can instead target the triggering tag. Owner must pass the validated tag, not rely on dispatch ref.
2. `release.yml:68-70`: `any(completed success)` accepts historical green despite a newer failed/pending required run for the same SHA. Literal jq reproduction with newest failure + older success returns true/exit 0. Latest qualifying exact-SHA evidence must be completed/successful; no failed/missing/stale fallback. Bind event/branch evidence to the intended checkout rather than mislabel synthetic merge results as direct commit tests.

Bounded checks executed using existing interpreter and in-memory inputs (no generated test files/full suite): AST/Python syntax, YAML parse, and every embedded shell `bash -n` passed; receipt checker accepts a valid receipt, rejects wrong tag/version/commit/missing or failed smoke/wheel name, bytes, hash; strict checksum parser rejects extra/duplicate/suffixed/malformed entries. Source inspection confirms checkout uses resolved immutable SHA, tag equality check exists, actual Git HEAD replaces workflow-trigger SHA for receipt provenance, expected-SHA build argument is present, and upload still lists exactly four output paths. Whole-job write permission remains a nonblocking hardening note. End-to-end dispatch and final candidate publication are not verified. Owner notified immediately; no review approval given.

### Corrected #524 — static PASS at b15ebbc

Re-reviewed **`b15ebbce8df8893d6ba172b08cf55b3008d24926`**, same base `3794b97...`, clean assigned review tree confirmed at this exact commit. Durable verdict: https://github.com/ajanderson1/agent-toolkit-cli/pull/524#issuecomment-6214254236 . Both prior P1 blockers resolved; no remaining blocking finding for this narrow dependency. Upload explicitly receives validated target tag. CI selects latest qualifying exact-SHA main push evidence and checks completed success, rather than historic `any(success)`.

Executed bounded **literal workflow shell** probes with mocked external responses, no on-disk test files: valid completed main push accepted; missing, newer failure/pending/cancelled, wrong SHA/branch, PR-only and dispatch-only evidence refused; newer green after older red accepted. Target-resolution shell accepted valid pair and refused mismatched resolution, short SHA and unsafe tag. Exact resolved SHA checkout, four upload paths, fail-on-missing, YAML/Python/shell syntax verified. Validator code unchanged since previous receipt tamper checks. No reviewer full suite/build/dispatch; no review524 files authored. Author reports 2450/5 pre-push; remote `38891934713` was IN_PROGRESS at this observation, so static PASS is not yet green-CI or merge approval. #518 remains held pending dependency merge and final regenerated candidate audit.

## Final #518 candidate audit — static PASS at 9938f6a

- User-requested fetch/checkout of own review518 worktree completed at exact `9938f6a098d332bb437798a74d5f7d5c9525df5a`; local report preserved. Worktree has only untracked `docs/reviews/`, no source edits. `git diff dae729c 9938f6a --check` passes.
- Parent is exactly `dae729cfd632fca2ab00744e31953c7fd6f00d04`. GitHub Git API confirms that merge tree equals the independently reviewed corrected #524 head `b15ebbce8df8893d6ba172b08cf55b3008d24926`; local comparison confirms no workflow, validator, tests or MkDocs config drift from that review.
- Only `.release-please-manifest.json`, `pyproject.toml`, `CHANGELOG.md` change (20 additions, 2 deletions). Parsed manifest and project both **5.10.0**; root Python release config, v-prefix and absence of forced release override verified.
- CLI `cli.py:18-21` and TUI `__init__.py:10-13` read installed `agent-toolkit` distribution metadata, with `unknown` fallback, no old literal version. Installed runtime behavior is reserved for p7 actual artifact QA. `docs/changelog.md` includes canonical `CHANGELOG.md` using snippets; all four campaign implementations plus #519/#517/#523/#524 are present in the new release section.
- Merged guarded-dispatch/receipt/upload integrity remains exactly as independently reviewed and probed above. Corrected #524 remote run `38891934713` was independently observed SUCCESS before its merge; main docs/test for the eventual release merge must still pass before dispatch.
- Final candidate API `statusCheckRollup: []` at audit time: **not green**. Previous candidate successes do not transfer. No reviewer full suite/build/smoke/dispatch, source edits, merge or publication.
- Concrete supported publication route after required evidence: integrator dispatches existing `release.yml` with required `release_tag=v5.10.0` and `expected_sha=<actual approved release merge SHA>`, using a ref containing the guarded workflow (main or that tag). Explicit target tag fixes branch-dispatch upload; exact merged-SHA main push test/docs must complete successfully or guard refuses. No tag deletion/re-push required or recommended.

### Final-candidate remote CI observation

Run **`38892406949` SUCCESS**, `pull_request`, API head `9938f6a098d332bb437798a74d5f7d5c9525df5a`, observed output **2450 passed, 5 skipped in 178.53s**. Checkout log uses synthetic merge **`cbf89f68813fe3621f6132848da25092d56071d4`** (parents base `dae729c...` and head `9938f6a...`). Independently compared GitHub Git API trees: both synthetic merge and candidate HEAD have tree **`80efd1e92010b23771ff37d5fa7672ef4a5108d3`**. Thus the tested integration tree exactly equals final candidate contents; this is no longer an empty-CI snapshot. p7 direct-candidate local QA remains pending at this observation. Dependency main `dae729c...` test `38892367937` and docs `38892367931` also succeeded; these do not substitute for the future release merge's checks.

### Observed candidate QA, merge and tag

Read p7 durable report https://github.com/ajanderson1/agent-toolkit-cli/pull/518#issuecomment-6214480453 and independently inspected `/private/tmp/atk-release-final-p7-9938/evidence/` logs: `full-suite.exit=0`, log **2450 passed, 5 skipped in 582.20s**; `docs.exit=0`, strict docs built in 0.78s; build-smoke log confirms version 5.10.0, wheel/sdist, packaged contents, all five CLI/TUI smoke checks and receipt/checksum validation completed. The docs dependency-origin banners are separate from strict omitted-nav warnings; no strict warning failure in this final run. Reviewer did not rerun any suite/build.

Independently observed #518 merged at `2026-10-16T11:27:44Z` as **`516d1a30508a3745dabd6b610eefcdea70817ece`**. Git API merge tree is **`80efd1e92010b23771ff37d5fa7672ef4a5108d3`**, exactly final candidate/tested tree. Git tag `v5.10.0` is a direct commit ref to that merge SHA. Notes-only release exists at https://github.com/ajanderson1/agent-toolkit-cli/releases/tag/v5.10.0 with **zero assets at this observation**: not artifact-verified publication. Main docs run `38893929370` SUCCESS, main test `38893929316` still IN_PROGRESS; integrator must wait before dispatch.

### Actual guarded publication — independent public verification PASS

Workflow dispatch **`38894345779` SUCCESS**, `headSha=516d1a30508a3745dabd6b610eefcdea70817ece`, `event=workflow_dispatch`. Main push test **`38893929316` SUCCESS** and docs **`38893929370` SUCCESS** independently observed before dispatch. Guard, full pre-release suite, build/smoke and upload executed by the workflow, not reviewer.

Reviewer anonymously fetched each public browser-download URL **entirely in memory**, without writing asset files or installing anything. Exact asset set is four, all uploaded; release is neither draft nor prerelease. Independently recomputed SHA-256 and bytes match GitHub API digests; wheel/sdist match receipt and strict exact two-entry SHA256SUMS. Receipt tag `v5.10.0`, version `5.10.0`, source commit `516d1a30508a3745dabd6b610eefcdea70817ece`, and all five required successful smoke fields match. Wheel internal METADATA/version, both entrypoints and packaged harness data verified; sdist embedded pyproject is 5.10.0. No source/config files were extracted or executed.

| Public asset | Bytes | Independently recomputed SHA-256 |
|---|---:|---|
| `agent_toolkit-5.10.0-py3-none-any.whl` | 389910 | `5cd665be16a7704e177eeb7f351d9adf483f2a4432ff64ad1b3b3c050385af6e` |
| `agent_toolkit-5.10.0.tar.gz` | 1670833 | `ffe35b5b4dffa0ebe5652ea9d6240517b3be0a8b7f0dfe18d6b76a3de307b723` |
| `deployment-receipt.json` | 772 | `6f6fbced83c463b49d9588859d3570f7f3f24c83ebb94e13f6893ddd33dd7e0c` |
| `SHA256SUMS` | 198 | `8001686279ef0e01f161305a0b55531f7cff35ba2a47e3d35a91ae9ef1fb04ed` |

Release: https://github.com/ajanderson1/agent-toolkit-cli/releases/tag/v5.10.0 . Public wheel hash also equals p7 final candidate wheel. Public sdist hash is its own build identity, independently verified against the publication receipt; it is not mislabeled as the earlier macOS candidate sdist. No PyPI publication claimed.

### Downloaded-artifact runtime QA — owner evidence PASS

Read pB's durable evidence directly at `/Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/qa-release-5-10-0-public-download-20261016/.qa-downloads/v5.10.0/verification-report.txt`. Its public asset bytes/hashes/provenance agree with this reviewer's separate anonymous in-memory verification. pB records disposable outside-checkout installed-wheel CLI and TUI **5.10.0**, successful CLI help/instructions list, headless marker **`TUI_HEADLESS_OK app=TUIApp screen=Screen size=Size(width=100, height=40)`**, actual terminal entrypoint rendering (expected interactive timeout), successful downloaded-sdist build/install, and a rebuilt wheel matching public wheel hash/size. Reviewer inspected this evidence; runtime execution belongs to pB, not reviewer. No additional suite or source edits were performed by reviewer.

**Release outcome: PASS.** Published v5.10.0 tag, approved merge, independent CI, confined candidate QA, guarded upload, public exact four-asset hash/receipt/provenance verification, and downloaded-runtime QA all have observed evidence. Nonblocking limitations recorded above are not silently represented as stronger directory/security guarantees. This is a GitHub release, not a PyPI publication.

## Gate closure

1. **Completed:** docs #523 and guarded dispatch #524 reviewed and merged; final exact-HEAD static audit above.
2. **Completed:** p7 exact-candidate full-suite/strict-docs/build/installed CLI+TUI smoke; actual final-head remote CI tested identical tree. Logs observed independently.
3. **Completed, integrator:** merge and exact `516d1a3...` main push test/docs SUCCESS followed by guarded dispatch SUCCESS. Reviewer never merges or authors fixes. Any new candidate SHA invalidates this exact-HEAD verdict.
4. **Completed:** independent public release assets/hash/receipt/version/provenance checks plus pB actual public downloaded-wheel CLI/TUI runtime and sdist build/install QA. Reviewer has not performed that write-producing operation. No remaining blocking release-audit gate.
