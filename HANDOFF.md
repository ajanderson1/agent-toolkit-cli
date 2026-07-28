# Issue #480 handoff

## Resume point

- Issue: https://github.com/ajanderson1/agent-toolkit-cli/issues/480
- Effective trust: **L2**.
- Worktree: `/Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/run-issue-480-1785230239`
- Branch: `swarm/run-issue-480-1785230239`
- Base: `origin/main` at `4bf53aaa969f359e1d7623ce6ab5ee48be86236a` (merged #479).
- No PR exists yet. Do not merge after opening it.
- The main checkout has unrelated dirty files and is behind origin; do not touch it.

## Implemented

Four atomic commits precede this checkpoint:

1. `907c554` — persisted JSON schema v1, atomic save, diagnostics, unknown-harness retention.
2. `11df659` — selection-aware composition across Skills, Instructions, Agents, MCPs, and Commands; import-time snapshots removed.
3. `54f9c00` — palette-only Settings screen, startup loading, live grid rebuild, visible diagnostics.
4. `e63d18c` — schema/TUI docs, MkDocs nav, AGENTS code map.

Locked semantics are preserved:

- `~/.agent-toolkit/tui-settings.json`, schema `agent-toolkit-tui-settings/v1`, and `AGENT_TOOLKIT_TUI_SETTINGS` override.
- Palette only; no settings keybinding.
- Candidates remain `MAIN_HARNESSES`; selection filters and never adds.
- MCP and Command columns are filtered without mutating CLI constants.
- `agent_toolkit_cli` never reads/imports TUI settings.
- Bad state defaults with a named status-bar notice; missing file is silent.
- Unknown harness names survive saves; empty selection is legal.
- No runtime dependency or intended lockfile change.

## L2 escalation resolution

The spec/AC said theme selection applies immediately and persists; the plan said apply on Save. AJ chose **option A**:

- theme selection atomically persists immediately while preserving committed harnesses;
- checkbox edits remain drafts;
- Save persists harness drafts, rebuilds all grids, and closes;
- Cancel/Escape discards only harness drafts and never restores the prior theme;
- the screen states this split explicitly.

Durable issue comment: https://github.com/ajanderson1/agent-toolkit-cli/issues/480#issuecomment-5102445437

Record this plan conflict and resolution in the PR body.

## Verification completed

- Fresh worktree baseline: `2038 passed, 2 skipped`.
- Persistence suite: `9 passed` (red observed first).
- Composition suite: `19 passed` (red observed first).
- TUI suite after UI wiring: `475 passed`.
- Strict docs build: `DISABLE_MKDOCS_2_WARNING=true uv run --frozen mkdocs build --strict` — pass.
- Final full suite: **`2142 passed, 2 skipped in 172.21s`**.
- Full-suite output: `assets/verification/issue-480/full-suite.txt` (the evidence tree is gitignored, so force-add it).

The plan checkboxes are marked complete through Task 5 Step 1. Steps 2–5 remain unchecked.

## Remaining work — do not broaden

### 1. Boundary scans

Capture outputs under `assets/verification/issue-480/`:

- `rg -n "MAIN_HARNESSES|_MCP_HARNESSES|DEFAULT_HARNESSES" src/`
  - judge every hit: declarations/imports/iteration reads only; no in-place mutation.
- `rg -n "agent_toolkit_tui" src/agent_toolkit_cli/`
  - expected no hits.
- `rg -n "INTERACTIVE_AGENTS|INTERACTIVE_HARNESSES" src/ tests/`
  - expected no hits.
- `git diff origin/main -- pyproject.toml uv.lock`
  - expected empty.

Write the scan output plus a short judgment file; do not treat a constant's source declaration as mutation.

### 2. CLI determinism

Use a temporary `AGENT_TOOLKIT_TUI_SETTINGS` path containing a non-default selection. Capture each command with the file present, move the file aside, rerun, and `cmp`:

- `uv run --frozen agent-toolkit-cli skill list`
- `uv run --frozen agent-toolkit-cli skill status`

Both pairs must be byte-identical. Store outputs/hashes/result under `assets/verification/issue-480/`. Stop if either differs.

### 3. Visual evidence

Use a temporary settings override, never AJ's real default file. Capture PNGs into `assets/verification/issue-480/` and write a one-line verdict per case:

1. `ctrl+p` palette showing **Settings**, then the Settings screen.
2. Theme change applies while the modal remains open; a second app instance loads it.
3. Draft-uncheck Pi, then change theme: persisted harness list still includes Pi.
4. Save Pi unchecked: Pi disappears from Skills, Agents, Commands, and global MCP; restart preserves it.
5. Cursor checkbox visibly says it has no standalone column to hide.
6. Empty selection leaves usable grids.
7. Malformed file launches defaults with a named status-bar notice.
8. Add `ghost-harness`, launch, save/change theme, and prove the JSON still contains it.

Textual `App.export_screenshot()` plus `rsvg-convert` is the established repository pattern (see `assets/verification/issue-479/capture_visual_evidence.py`). A deterministic capture script may be committed with the evidence.

Also write `assets/verification/issue-480/manifest.md` with commands, exit codes, commit SHA, artifacts, and overall visual verdict.

### 4. Finish and open PR

- Mark Task 5 Steps 2–5 checked in `docs/superpowers/plans/2026-07-28-480-tui-settings-screen.md`.
- Force-add ignored evidence: `git add -f assets/verification/issue-480/`.
- Final commit with `Device: atlas` trailer. Remove `HANDOFF.md` before the final commit if it is not useful in the PR; otherwise explain it.
- Invoke/read `superpowers:verification-before-completion` and satisfy it before claiming green.
- Confirm clean status and every authored commit has `Device: atlas`.
- Push `swarm/run-issue-480-1785230239`.
- Open, do not merge, a PR against `main` using the issue title and `Closes #480`.
- PR body must include summary, automated evidence, one-line visual verdict, no-runtime-dependency/CLI-boundary result, escalation resolution, and these caveats:
  - settings Save rebuilds all grids and existing `set_rows()` semantics clear pending queues;
  - agent harness derivation now receives the real scope (latent import-time inconsistency removed).
- Add the final issue comment with PR URL and evidence path.
- Leave this worktree intact until merge.

## Lockfile trap

Plain `uv run ...` updates the stale local `uv.lock` package version from `5.3.0` to `5.5.0`. This issue must not carry that incidental change. It has been restored after the full suite. Prefer `uv run --frozen ...` for remaining commands and verify `uv.lock` stays clean.
