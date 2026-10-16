# Final current-documentation audit and author verification

Recorded at **2026-10-16T18:41:55.198299+00:00**, from the actual UTC clock. Branch date is an identifier, not evidence of capture time.

## Authority and boundaries

Final feature base: `b7b5200d58684fbd9699c29c3fd6c9719f4924a7` (PR #535 merged; independently checked). New Worktrunk-owned docs branch, no main/other-tree/live-assets writes. Issue promises and the earlier readiness handoff were treated as historical, not implementation authority. No package version/CHANGELOG edits; release PR #528 waits for docs merge. PM owns review disposition, merge and release.

## Coverage

Every current tracked Markdown reference below was revised or verified-current; all 55 generated harness pages are individually covered by regeneration byte-parity and local-link/anchor tests. This is source/help alignment, **not a new live upstream compatibility certification**. Historical specs/plans/reviews/audits/research/solutions and CHANGELOG retain history.

Root `README.md`: thoroughly reorganized orientation/install/quickstart/usage/config/media/architecture/contributing/license. Root `AGENTS.md`: factual code map, plural groups, six kinds, storage and pre-push corrected; operation/trust retained. `STRATEGY.md`: factual kind list/visibility statements corrected, not product direction. `mkdocs.yml`: description corrected; strict validation, nav/exclusions/redirects preserved. Site CSS/JS fold inspected, unchanged; changelog include verified.

| Current page | Disposition / evidence basis |
|---|---|
| `docs/agent-toolkit/bundles.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/agent-toolkit/cli.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/agent-toolkit/harness-matrix.md` | Reconciled/derived; parsed final catalog/verdicts; scope/adapter caveats; parity tests. |
| `docs/agent-toolkit/lock-files.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/agent-toolkit/roadmap.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/agent-toolkit/skill-lock.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/agent-toolkit/tui-settings.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/agent-toolkit/tui.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/asset-types/agents.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/asset-types/commands.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/asset-types/instructions.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/asset-types/mcp.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/asset-types/pi-extensions.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/asset-types/skills.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/assets/screenshots/README.md` | Replaced placeholders with actual isolated PNG/SVG, assertions, reproduction and visual verdict. |
| `docs/changelog.md` | Verified current include-only router; ReleasePlease-owned CHANGELOG preserved. |
| `docs/glossary.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/harnesses/adal.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/aider-desk.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/amp.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/antigravity.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/augment.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/bob.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/claude-code.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/cline.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/codearts-agent.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/codebuddy.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/codemaker.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/codestudio.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/codex.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/command-code.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/continue.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/cortex.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/crush.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/cursor.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/deepagents.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/devin.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/dexto.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/droid.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/firebender.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/forgecode.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/gemini-cli.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/github-copilot.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/goose.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/hermes-agent.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/iflow-cli.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/junie.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/kilo.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/kimi-cli.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/kiro-cli.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/kode.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/mcpjam.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/mistral-vibe.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/mux.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/neovate.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/openclaw.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/opencode.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/openhands.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/paperclip.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/pi.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/pochi.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/qoder.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/qwen-code.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/replit.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/roo.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/rovodev.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/tabnine-cli.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/trae-cn.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/trae.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/warp.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/windsurf.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/harnesses/zencoder.md` | Regenerated; parsed per-scope Instructions/subagent SSOT + skills catalog/support constants; all-page byte parity and links. |
| `docs/index.md` | Revised/verified against final CLI help, per-kind facades, TUI state/adapters and selected behavior tests. |
| `docs/matrix.md` | Reconciled/derived; parsed final catalog/verdicts; scope/adapter caveats; parity tests. |

## Source and help basis

- Dispatcher `cli.py`, every registered per-kind group/subcommand and isolated `--help`: **75 invocations** including aliases; no library writes. Canonical plural groups, actual singular aliases and nonuniform verbs/arguments/flags checked.
- Scope: per-kind `_common.py`, Skills install/uninstall in group module, `_paths_core.default_scope`, and default/scope parity tests. No blanket global default; Commands/Bundles detect any source-backed project lock, others differ.
- Skills: source/path/lock/Git modules, collection registration/catalog/transaction/install, update/push/reset/remove facades; real children and persisted source/ref groups, shared parent, owned subpath PR publishing, read-only refusal, missing-document health, conservative root/nested refusal, targeted legacy reconciliation and local-work preservation.
- Instructions: matrix parser, pointer adapters/install, directory-slot/physical-node/source-chain tests; user-owned canonical bytes, filesystem installation truth, ignored/preserved legacy locks, guarded explicit adoption and partial retry.
- MCP: manifest/library, install/config adapters and import/migrate/doctor/remove; global authority vs selected-scope projections, OpenCode native `mcp` key, four concrete adapters, project Standard, Pi-only bearer variable **names**. JSON neighbor entries survive but formatting is not byte-preserved.
- Other kinds: enabled agent adapters/Standard reader sets and ownership sidecars; Commands Standard/Pi/Gemini defaults and explicit deprecated global Codex; Pi git/npm/local inventory and noninteractive untracked packages. Catalog rows are not universal supported adapters.
- Bundles: manifest/dispatcher/orchestrator; Skills/Agents/Pi only, already-present skip, cleanup attempts/failure reporting, structural-only validate, no Commands/Instructions or installed MCP support.
- TUI: actual app/grid/state/settings behavior and focused tests: all-kind Apply/Diff/Revert, per-kind retry differences, both scopes, explicit Refresh clears active queue vs internal preservation, confirmed preference discard, collections all/none/mixed/full membership, plural sidebar/shortcuts, bold repo/final component, clipping rather than invented truncation.

## Bounded implementation deltas

The only runtime source edit is **two help-example comments** in `commands/skill/__init__.py`: project canonical lives in the external store, and list infers project when its lock exists. No executable product behavior changed.

Generator fix: final SSOT had eight Instructions columns (including Global verdict) but generator expected seven, reproducibly refusing regeneration. Added scope field/parsing/rendering, shared Commands readers and truthful support/adapter language. Regression tests first failed on parser/Commands gaps, then passed. Generated pages are not hand-edited.

Capture/check tests/scripts only: source-asserted isolated fixture rendering, local-link/anchor/media/help checks, all-generated-page/nav parity. No new Python dependencies, provider policy, feature or live configuration changes.

## Fresh image receipt and visual assertion

- PNG written at **2026-10-16T18:27:16.953385+00:00** (filesystem UTC timestamp, observed after capture).
- `assets/agent-toolkit-cli-tui.png` SHA256: `0ff00c36da9b940710c66a8531a30bbf2778781645b328f59b2e3a61df63f71f`.
- Source `assets/agent-toolkit-cli-tui.svg` SHA256: `2049da49d984417d942bb93b412f395a93d7bfde74e5852302e61cffafe61970`.
- Identical site copy: `docs/assets/screenshots/tui-overview.png`; 1848×831 PNG from the real 150×32 Textual viewport.
- `scripts/capture_docs_tui.py` asserts CLI/TUI imports from owned source after isolated HOME/config/library initialization; local Git only, actual source-batch install, seven real children, one collection, two queued-but-unwritten operations. No browser/live operator configuration.
- **Visual PASS:** all six clean plural sidebar labels, real expanded collection/children, cyan mixed vs yellow pending removal, global scope/two pending edits, bold REPO/final demo-project component visible. Source cell clipping is actual behavior; full identity remains in Info.
- SVG plaintext privacy assertions and Gitleaks stdin scan passed (94,648 bytes); PNG metadata inspected, only generated media/no host secrets. Synthetic source and disposable temporary path only.

## Author checks actually observed before freeze

- Focused help/docs/harness/matrix/packaging/scope/collections/Instructions/TUI/settings suite: **195 passed in 43.91s**, followed by added all-generated-page parity test (**8 generator tests passed**).
- Full **`uv run pytest -q`: 2643 passed, 10 skipped in 307.46s**. 600s budget explicitly allocated; one author full job, not overlapping another job started by this writer.
- `make docs-build` strict: passed; upstream dependency advisory text is not a project docs validation failure.
- Generator repeated: **57 outputs byte-identical** (matrix, 55 harness pages, nav config).
- Current Markdown/README relative links, anchors and media assertions: passed. Strict build preserves nav and all six legacy kinds→asset-types redirects.
- Six bounded public URL HEAD checks: HTTP 200 for published docs, repository, releases, uv docs, Textual docs, vercel-labs/skills. Not an exhaustive external URL/research revalidation.
- `git diff --check` and authored diff/SVG leak checks: passed. Complete committed-range leak scan is a delivery check after commit.
- Full suite rewrote tracked historical `assets/verification/515/inventory.svg`. Preserved generated SVG/patch outside repository; exact test replay produced identical bytes after Rich ID normalization. Differences versus historical tracked output were final-source collection filter hint/ellipsis plus render IDs; only that proven task-generated artifact was restored. No blanket reset/clean.

Normal mandatory pre-push full suite, remote push/PR, **fresh independent exact-head review and actual exact-head green CI remain separate delivery gates**; this author audit is not approval. PM owns merge/release.
