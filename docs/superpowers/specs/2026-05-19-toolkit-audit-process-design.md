# Toolkit audit process — design

**Status:** Spec (awaiting user review)
**Date:** 2026-05-19
**Repo:** `agent-toolkit-cli`
**Companion PR:** `agent-toolkit` (demo asset additions)

## 1. Purpose

The toolkit audit is a development/QA process — not a shipped feature, not a CLI subcommand, not CI — that for every supported `(kind × harness)` cell visibly demonstrates the CLI's behavior across its full operational surface, surfaces asymmetries in the harness/kind matrix, catches regressions, and produces a living findings document.

It belongs in the CLI repo because it tests CLI behavior.

## 2. Outputs

The audit produces three artifact classes, all in this repo:

- **Findings doc** — `docs/audit/2026-05-19-toolkit-audit.md`. Living. Scaffolded by `audit/build-doc.sh`; cell findings are hand-written prose.
- **Per-cell demos** — `audit/demos/<kind>-<harness>.sh`. One self-contained narrated tmux demo per supported cell, with hard assertions at the end that exit non-zero on regression.
- **Shared helpers** — `audit/lib/{sandbox,narrate,assert}.sh` plus `audit/lib/code_probe.py`. Pure bash (and one small Python introspection helper), deterministically testable.

Plus the matrix discoverer (`audit/discover-matrix.sh`), scaffolder (`audit/build-doc.sh`), and optional `audit/run-all.sh` runner.

## 3. Directory layout

```
audit/
  build-doc.sh
  discover-matrix.sh
  run-all.sh
  lib/
    sandbox.sh
    narrate.sh
    assert.sh
    code_probe.py
  demos/
    skill-claude.sh
    skill-codex.sh
    …                       one script per supported cell
docs/
  audit/
    2026-05-19-toolkit-audit.md
tests/
  audit/
    test_sandbox.sh
    test_assert.sh
    test_code_probe.sh
```

Audit lives at the repo root (not under `tests/`) because demos are human-facing investigation artifacts, not pytest. Helpers are bash, so their tests are bash.

## 4. Sandbox model

Each demo opens with `sandbox::init` which:

1. Creates a tmpdir via `mktemp -d -t agent-toolkit-audit.XXXXXX`.
2. Sets the harness env vars empirically verified to redirect that harness's config: `HOME`, `XDG_CONFIG_HOME`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, plus per-harness equivalents for OpenCode, Gemini CLI, and Pi (exact var names verified per-harness during helper implementation; `HOME` is the universal fallback).
3. Exports `AGENT_TOOLKIT_REPO=~/GitHub/agent-toolkit` (or honors a pre-set value). Demos treat the toolkit repo as read-only — they only read assets and write into the sandbox `HOME`.
4. Registers `trap 'rm -rf "$tmp"' EXIT` so cleanup happens automatically even on assertion failure.

The real `~/.claude/`, `~/.codex/`, etc. are never touched.

## 5. Demo assets

Two flavors, both **permanent** assets in the toolkit repo:

- **Already exist:** `skills/demo-skill/`, `mcps/demo-mcp/`, `plugins/companion-html/`.
- **To be added (companion PR in `agent-toolkit`):** `demo-agent`, `demo-command`, `demo-hook`, `demo-pi-extension`. Minimal, self-evidently-demo bodies. Frontmatter `apiVersion: agent-toolkit/v1alpha2`, `spec.origin: first-party`, descriptions of the form *"Audit/demo asset for `<kind>`."*

There is no ephemeral scaffolding. The toolkit repo owns its demo inventory.

## 6. Narration & assertion contract

`audit/lib/narrate.sh` exposes:

```bash
step "Step 1: link demo-skill into the user-scope claude target"
run "agent-toolkit link user claude skill:demo-skill"
show "$HOME/.claude/skills/demo-skill"
pause 1.5
```

`run` echoes the command in bold then executes it. `show` does `ls -la` + `readlink` for symlinks, `head -20` for files. `pause` honors `PAUSE_SCALE` for slow-mode demos. Output is colorized on TTY, plain when piped.

`audit/lib/assert.sh` runs at the **end** of each demo:

```bash
assert_symlink_exists  <path>
assert_symlink_target  <path> <expected-target>
assert_no_symlink      <path>
assert_file_contains   <path> <substring>
assert_exit_code       <code> -- <cmd> [args…]
assertions::finish     # exits 1 if any failed, 0 otherwise
```

Assertions are accumulated (not fail-fast) so the human sees the full picture. The tmux pane does not auto-close — results remain visible after detach/reattach.

## 7. Tmux orchestration

Each demo script is self-hosting via a re-exec pattern:

```bash
if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-$(basename "$0" .sh)"
  tmux kill-session -t "$session" 2>/dev/null || true
  tmux new-session -d -s "$session" "AUDIT_INSIDE_TMUX=1 $0"
  echo "tmux attach -t $session"
  exit 0
fi
# … real body runs inside tmux …
```

One session per cell, named `audit-<kind>-<harness>`. No central pane.

## 8. Per-cell write-up template

Cells in the findings doc use this template:

```markdown
### <kind> × <harness>

**Overview** — one-paragraph orientation.

**Mechanics** — what the CLI actually does behind the scenes for this combo.

**Operations**
  - *Lifecycle* (link/unlink, user+project)
  - *Validation* (check/fix/doctor)
  - *Authoring* (new/ingest)
  - *Inspection+Robustness* (list/diff/inventory)

**Human-edit robustness** — hand-edited projection, deleted symlink, edited `.agent-toolkit.yaml`.

**Demo script** — `audit/demos/<kind>-<harness>.sh` (`tmux attach -t audit-<kind>-<harness>`)

**Findings**
  - ✅ …
  - ⚠️ …
  - ❌ …
```

Each cell's findings are hand-written. The template is what the scaffolder inserts for new cells; it is not regenerated thereafter.

## 9. Support-matrix discovery

`audit/discover-matrix.sh` produces TSV (`kind \t harness \t source \t supported`) from three independent probes:

- **Code probe.** Introspect CLI internals via `audit/lib/code_probe.py`, which imports `agent_toolkit_cli.harness_adapters` and `agent_toolkit_cli.commands.link` to enumerate the `(harness, kind) → target_dir` table. (The CLI's `inventory --json` may also expose enough; the Python helper is the authoritative fallback.)
- **Schema probe.** `jq` over `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json`, reading each kind's `spec.harnesses` enum.
- **Empirical probe.** For each pair claimed by code OR schema, run a one-shot `agent-toolkit link user <harness> <kind>:demo-<kind>` in a throwaway sandbox and check whether anything materialized.

Disagreements between sources are themselves findings.

## 10. Findings doc structure & lifecycle

`docs/audit/2026-05-19-toolkit-audit.md` has four top-level sections:

```
# Toolkit Audit — 2026-05-19

## Rollup
   Top-line counts (passing/failing/warning), last-run timestamp,
   hand-curated prioritized issues list.

## Support matrix
### Code-derived
### Schema-derived
### Empirical
### Disagreements

## Cells
### skill × claude
…
### pi-extension × pi
```

**`audit/build-doc.sh` semantics — idempotent merge:**

1. Re-render the four matrices and disagreements block. These regions live between `<!-- BEGIN_AUDIT:matrix --><!-- END_AUDIT:matrix -->` markers, fully regenerated each run (same pattern as the toolkit repo's AGENTS.md auto-regions).
2. For each supported cell, ensure a `<!-- BEGIN_AUDIT:cell <kind>-<harness> --><!-- END_AUDIT:cell <kind>-<harness> -->` marker pair exists. If absent, insert a fresh stub from §8. If present, leave contents untouched — human prose is sacred.
3. Newly-unsupported cells (previously supported, now empty) get a `⚠️ NO LONGER SUPPORTED — review and remove` banner inserted just inside their BEGIN marker. The human decides whether to delete.
4. The Rollup section is regenerated each run **except** the prioritized-issues list, which lives between its own markers and is hand-curated.

**Pass/fail integration.** `audit/run-all.sh` runs every demo, captures exit codes, writes one line per cell into `audit/.last-run.tsv`. `build-doc.sh` reads this and decorates each cell heading with `[PASS]` / `[FAIL]` / `[STALE]`; the Rollup counts come from the same file.

## 11. Op coverage per cell

Every supported cell's demo and write-up covers four op groups:

1. **Lifecycle** — `link` then `unlink`, at both `user` and `project` scope.
2. **Validation** — `check`, `fix`, `doctor`.
3. **Authoring** — `new` (scaffold an asset), `ingest` (import an external asset).
4. **Inspection + robustness** — `list`, `diff`, `inventory`, plus three deliberate-sabotage scenarios:
   - A human hand-edits the projection file.
   - A human deletes the symlink.
   - A human edits `.agent-toolkit.yaml` to drop the asset.

The demo narrates each sub-step; the assertions at the end verify the expected end state.

## 12. Implementation sequencing

1. **Helpers first (this repo).** `sandbox.sh`, `narrate.sh`, `assert.sh`, plus shell tests under `tests/audit/`. Verification: shell tests pass; manual smoke of `sandbox::init` shows env vars set and cleanup running.
2. **Companion PR in toolkit repo.** Author `demo-agent`, `demo-command`, `demo-hook`, `demo-pi-extension` with minimal bodies and valid v1alpha2 frontmatter. Land before any cell beyond `skill × claude`. Verification: `agent-toolkit check` passes in the toolkit repo.
3. **Reference cell: `skill × claude`.** `audit/demos/skill-claude.sh` end-to-end. All four op groups + robustness scenarios. Verification: script exits 0 on a clean sandbox; deliberate sabotage flips it to exit 1.
4. **Support-matrix discovery.** `audit/lib/code_probe.py`, `audit/discover-matrix.sh`. Verification: TSV output matches a hand-computed expected matrix snapshotted in tests.
5. **Doc scaffolder.** `audit/build-doc.sh`. Verification: empty `docs/audit/` produces the right skeleton; second run is a no-op; hand-edited cell prose survives a re-run; newly-unsupported cells gain the banner.
6. **Fan out remaining cells.** One demo per supported cell, ordered symmetric → asymmetric (skills → agents → commands → hooks → plugins → mcps → pi-extensions across each harness). Helper gaps surfaced mid-fan-out get fixed in the shared helper, not forked.
7. **`run-all.sh` + rollup integration.** Wire pass/fail into the doc. Verification: forced-fail one cell, confirm the Rollup reflects it.

Worktree: `.worktrees/audit-process-<timestamp>/` per the global convention. The toolkit-repo companion PR is a separate worktree in that repo.

TDD scope: helpers (steps 1, 4, 5) get shell tests. Demos (steps 3, 6) are themselves integration tests — their own assertions are the test.

## 13. Non-goals

- Not a `agent-toolkit audit` subcommand. Bolting it onto the CLI would either over-constrain agent judgment or become a thin shell wrapper. Scripts + doc is the right shape.
- Not CI-gated. The audit runs on-demand. Demo exit codes give it the *ability* to be CI-wired later, but that's not in scope here.
- Not auto-generated findings prose. The point of the audit is human investigation; auto-summarising would defeat it.
- Not coverage of empty cells. Only supported cells get write-ups; the matrix surfaces the empties.

## 14. Open seams (deferred, not blockers)

- Exact env-var names for OpenCode / Gemini CLI / Pi sandbox redirection — verified during step 1 implementation, encoded in `sandbox.sh`.
- Whether `inventory --json` is sufficient for the code probe or `code_probe.py` is strictly required — decided during step 4.
- Whether to add a `audit/regenerate.sh` convenience wrapper combining `discover-matrix.sh` + `build-doc.sh` — punted; trivially added later if `run-all.sh` doesn't subsume it.
