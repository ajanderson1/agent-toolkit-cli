# Multi-kind catalogue — local verification

## Source and delivery

- CLI branch: `feat/multi-kind-catalog`.
- CLI implementation commit: `52947add96ff9b333221766ce51b70a155cc4501`.
- Base: `15132c5d6785a35c152cb1749a4b7bd48341ff36` (current 7.0.0 code plus spec).
- CLI worktree: `.worktrees/feat-multi-kind-catalog` in the canonical CLI checkout.
- Catalogue checkout: `/Users/ajanderson/GitHub/agent-toolkit/catalog`.
- Catalogue branch: `feat/multi-kind-catalog`; implementation commit:
  `2e789805ada1d8be96b8837bf353bc5d9d131856`.
- Local commits only: no push, merge into CLI main, release, fleet update or live
  library/Pi-settings change. Package version/CHANGELOG were not edited.

## Implemented

Typed version-2 entries for skills, agents, commands and Git/native npm Pi
extensions; one shared subscription/list/validation utility; per-kind CLI catalogue
operations and ordinary inventory joins; non-advancing Git reuse with source/ref/
path/agent-shape validation; explicit confirmed native npm installation without a
Toolkit npm registry; timestamped Git checks; one shared asynchronous TUI snapshot
and one cross-kind Apply revalidation, with failed intents retained and npm
catalogue-only rows read-only. Source-backed Pi controls cannot accidentally
redispatch a Git choice to native npm by a colliding name.

Catalogue admission requires revision-bound fit, quality, functional, security and
license evidence and checks actual upstream packaging without executing its code.
Published new Git entries require full reviewed commit pins; npm records include
archive integrity and select one version per native package identity. Evidence is
an accountable curator judgement, not an automated proof of content quality.

## Tests and documentation

The new tests were observed failing before implementation. Focused skills baseline:
55 passed; integrated focused run: 131 passed. Final entire test corpus was covered
in two independent partitions with separate caches:

```text
uv run pytest -q tests/test_cli --tb=short -o cache_dir=/tmp/atk-multi-catalog-cli-cache
2142 passed, 10 skipped in 440.86s

uv run pytest -q --ignore=tests/test_cli --tb=short -o cache_dir=/tmp/atk-multi-catalog-rest-cache
1066 passed in 300.84s
```

Total: **3,208 passed, 10 skipped**. The skipped tests were rerun with `-rs`; they
cover intentionally unavailable/native scopes, global-only registry cases, a test
that would touch real `~/.claude`, and the known cross-tool global-lock mismatch.
They are not new catalogue test failures.

The first serial full-suite attempt reached 94% before the 20-minute command limit.
Its three observed failures were reproduced and fixed (literal command-coverage
invocations and preserving the injectable skills upstream-check seam), then the
complete partitioned rerun above passed. No timed-out pytest remained running.

`make docs-build` (strict), `python -m compileall -q src`, and Git whitespace checks
passed. MkDocs printed its existing upstream ecosystem advisory; the strict build
completed successfully.

Logs: `/tmp/atk-multi-catalog-cli.log`, `/tmp/atk-multi-catalog-rest.log`.

## Catalogue conversion

The independent catalogue's 109 existing skills retain every original key,
description, source, path and ref. Only the envelope and explicit kind/sourceType
were added. Schema validation passes. Admission against the previously accepted
version-1 manifest reports **0 new/changed selectors**, without manufacturing
historical quality approvals. The catalogue guide now requires inspection evidence
for genuinely new/changed entries. No agents, commands or extensions were silently
seeded: those still require their actual upstream admission inspection.

## Wheel identity and installed-artifact smoke

Built with `uv build` from implementation commit
`52947add96ff9b333221766ce51b70a155cc4501`:

```text
dist/agent_toolkit-7.0.0-py3-none-any.whl
SHA-256: ad70572727d34aec314edcb21492229e0735b7a0ce3faf8a003ffae2f85e176b
```

The version alone does not identify this unreleased feature build. The wheel was
installed into `/tmp/atk-catalog-wheel-env.HuQ5S2`, not into the user's environment.
`/tmp/atk_multi_catalog_wheel_smoke.py` passed from a disposable HOME/project using
real local Git remotes and the installed entrypoint:

- Five mixed-type listings, with shared keys across kinds.
- Add, explicit project enable and pinned Git checks for all four Git kinds.
- Native npm Add refusal and declined installation confirmation; no native npm
  package downloaded or installed, no extension code executed.
- Unsubscription retains all acquired content/projections.
- The actual 109-entry version-2 catalogue parses and passes unchanged-selector
  admission against the accepted base.
- Imports resolve to the wheel's `site-packages`, not the editable worktree.

Actual third-party asset quality, model behavior and live Pi session loading were
not certified by synthetic fixtures. npm archive/script suppression and native
installation delegation are covered by isolated fixture/mocked tests, not a live
package installation. No production catalogue publication or consumer deployment
was performed.
