# Toolkit Audit — 2026-05-19

## Rollup

<!-- BEGIN_AUDIT:rollup -->
Last scaffolded: 2026-05-19T17:31:56Z

**Results:** 13 PASS · 7 FAIL across 20 supported cells. 5 of 7 FAILs are intentional (cells documenting asset-metadata gaps); 2 surface real CLI bugs that affect claude under multiple kinds.

### Prioritized issues

1. **`unlink <kind>:<slug>` is a no-op for symlink-kinds on claude.** Replicated by `agent × claude`, `command × claude`. The command exits 0 with "Already in sync — 0 assets linked" but leaves the symlink on disk. Bulk `unlink user claude` (no slug) works correctly; the per-asset selector form is broken. **Affects:** claude agents, claude commands, likely claude skills/hooks if the same call shape is exercised. Severity: high — user-visible, exit-code-confusing.

2. **Stale projections aren't pruned on reconcile.** After removing an asset from `.agent-toolkit.yaml`, re-running `link user <harness>` (no slug args) leaves the previously-linked artefact intact. Surfaces in `agent × claude`, `command × claude`, all three implementing MCP cells (`mcp × {claude, codex, opencode}`). Root cause for MCPs documented in `mcp × codex`: ownership tracking is `previously_allowed ∪ desired_names` — with both empty after the edit, the orphan is treated as hand-rolled. Severity: high — silent state drift.

3. **Doctor's `symlink-integrity` group is blind to replaced symlinks under claude.** When a projected symlink is replaced by a regular file, `check_path.exists()` is True and `check_path.is_symlink()` is False — the slot falls into neither branch in `doctor/symlinks.py:73–83`. Confirmed for `skill × claude`, `agent × claude`, `command × claude`, `plugin × claude`. **Not present** for codex (skill), opencode, pi — so it's a claude-specific gap. Severity: medium — silent gap in the health-check surface.

4. **Doctor crashes (uncaught exception, traceback to stderr) on broken TOML config under codex.** `mcp × codex` recon: invalid `~/.codex/config.toml` raises `tomlkit.exceptions.UnexpectedCharError` from `doctor`, exit 1, no `FAIL`-status reporting. Severity: medium — doctor should surface as FAIL, not crash.

5. **`(claude, hook)` has no adapter; `link` silently degrades to allowlist-only.** `hook × claude` recon: `get_adapter("claude", "hook")` returns `UnimplementedAdapter`. The link adds the slug to `.agent-toolkit.yaml` and prints `"no MCP adapter for harness claude yet — skipping"` (misleading message — the hook adapter is not an MCP adapter). `~/.claude/settings.json` is never written; `hooks/demo-hook.sh` is never materialised. Severity: high — feature appears wired (target dir in `_USER_TARGETS`) but is unimplemented.

6. **`--exit-code` only trips on `FAIL`, not `WARN`.** `doctor --exit-code` returns 0 when worst status is WARN. Sandbox state always produces WARN-level "many unlinked assets" → `--exit-code` is a weaker gate than the name implies. Severity: low — by design, but the contract is confusing.

7. **Project-scope MCP link is a silent no-op if `.mcp.json` doesn't pre-exist.** `mcp × claude` recon: `ClaudeAdapter.config_target()` returns `None` when the file is absent, so the link does nothing without reporting. Severity: medium — silent failure.

### Cross-harness divergences worth noting

- **Doctor's replaced-symlink blind spot is claude-specific.** Codex / opencode / pi all detect the replacement.
- **Pi user-vs-project paths are asymmetric.** User scope: `~/.pi/agent/<kind>/`; project scope: `.pi/<kind>/` (no `agent/` infix). Affects skills, agents, pi-extensions identically.
- **Codex skill projection stages via a local cache** (`~/.codex/.agent-toolkit-cache/`) — direct symlink would not pass through the codex translator. Different mechanism from claude.
- **OpenCode projection shape is mixed by kind.** Skills use `dir-with-file-symlink` (real directory, inner `SKILL.md` symlinked into cache). Agents and commands use raw file symlinks straight into the cache.

### Asset-metadata gaps (planned follow-up — not CLI bugs)

- **No asset in the toolkit declares `gemini` as a supported harness.** Affects all gemini cells: every `link user gemini <kind>:<slug>` is rejected at the per-asset gate. CLI infrastructure is in place (`_USER_TARGETS` populated, `GeminiAdapter` exists for MCPs). Fix: opt assets in by adding `gemini` to their `spec.harnesses`.
- **`demo-hook` declares only `[claude]`.** `hook × codex` is rejected by the same gate.
- **`demo-mcp` declares `[claude, codex, opencode]`.** `mcp × gemini` is rejected.

### T11 empirical-probe false negative

`plugin × claude` was flagged as a disagreement (code=true, empirical=false) but the cell demo shows it works correctly — the probe didn't look in `$CLAUDE_CONFIG_DIR/plugins/`. Fix: improve `discover-matrix.sh`'s empirical heuristic. Severity: low — only affects the probe, not the CLI.
<!-- END_AUDIT:rollup -->

## Support matrix

<!-- BEGIN_AUDIT:matrix -->
### Code-derived

|         | claude | codex | gemini | opencode | pi |
|---------|:---:|:---:|:---:|:---:|:---:|
| agent | ✓ | — | ✓ | ✓ | ✓ |
| command | ✓ | — | ✓ | ✓ | — |
| hook | ✓ | ✓ | — | — | — |
| mcp | ✓ | ✓ | ✓ | ✓ | — |
| pi-extension | — | — | — | — | ✓ |
| plugin | ✓ | — | — | — | — |
| skill | ✓ | ✓ | ✓ | ✓ | ✓ |

### Schema-derived

|         | claude | codex | gemini | opencode | pi |
|---------|:---:|:---:|:---:|:---:|:---:|
| agent | ✓ | ✓ | ✓ | ✓ | ✓ |
| command | ✓ | ✓ | ✓ | ✓ | ✓ |
| hook | ✓ | ✓ | ✓ | ✓ | ✓ |
| mcp | ✓ | ✓ | ✓ | ✓ | ✓ |
| pi-extension | ✓ | ✓ | ✓ | ✓ | ✓ |
| plugin | ✓ | ✓ | ✓ | ✓ | ✓ |
| skill | ✓ | ✓ | ✓ | ✓ | ✓ |

### Empirical

|         | claude | codex | gemini | opencode | pi |
|---------|:---:|:---:|:---:|:---:|:---:|
| agent | ✓ |   | — | ✓ | ✓ |
| command | ✓ |   | — | ✓ |   |
| hook | — | — |   |   |   |
| mcp | ✓ | ✓ | — | ✓ |   |
| pi-extension |   |   |   |   | — |
| plugin | — |   |   |   |   |
| skill | ✓ | ✓ | — | ✓ | ✓ |

### Disagreements

- agent × codex: code=false, schema=true
- agent × gemini: code=true, schema=true, empirical=false
- command × codex: code=false, schema=true
- command × gemini: code=true, schema=true, empirical=false
- command × pi: code=false, schema=true
- hook × claude: code=true, schema=true, empirical=false
- hook × codex: code=true, schema=true, empirical=false
- hook × gemini: code=false, schema=true
- hook × opencode: code=false, schema=true
- hook × pi: code=false, schema=true
- mcp × gemini: code=true, schema=true, empirical=false
- mcp × pi: code=false, schema=true
- pi-extension × claude: code=false, schema=true
- pi-extension × codex: code=false, schema=true
- pi-extension × gemini: code=false, schema=true
- pi-extension × opencode: code=false, schema=true
- pi-extension × pi: code=true, schema=true, empirical=false
- plugin × claude: code=true, schema=true, empirical=false
- plugin × codex: code=false, schema=true
- plugin × gemini: code=false, schema=true
- plugin × opencode: code=false, schema=true
- plugin × pi: code=false, schema=true
- skill × gemini: code=true, schema=true, empirical=false

<!-- END_AUDIT:matrix -->

## Cells

### agent × claude [FAIL]

<!-- BEGIN_AUDIT:cell agent-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/agent-claude.sh` (`tmux attach -t audit-agent-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell agent-claude -->

### agent × gemini [FAIL]

<!-- BEGIN_AUDIT:cell agent-gemini -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/agent-gemini.sh` (`tmux attach -t audit-agent-gemini`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell agent-gemini -->

### agent × opencode [PASS]

<!-- BEGIN_AUDIT:cell agent-opencode -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/agent-opencode.sh` (`tmux attach -t audit-agent-opencode`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell agent-opencode -->

### agent × pi [PASS]

<!-- BEGIN_AUDIT:cell agent-pi -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/agent-pi.sh` (`tmux attach -t audit-agent-pi`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell agent-pi -->

### command × claude [FAIL]

<!-- BEGIN_AUDIT:cell command-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/command-claude.sh` (`tmux attach -t audit-command-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell command-claude -->

### command × gemini [FAIL]

<!-- BEGIN_AUDIT:cell command-gemini -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/command-gemini.sh` (`tmux attach -t audit-command-gemini`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell command-gemini -->

### command × opencode [PASS]

<!-- BEGIN_AUDIT:cell command-opencode -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/command-opencode.sh` (`tmux attach -t audit-command-opencode`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell command-opencode -->

### hook × claude [PASS]

<!-- BEGIN_AUDIT:cell hook-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/hook-claude.sh` (`tmux attach -t audit-hook-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell hook-claude -->

### hook × codex [FAIL]

<!-- BEGIN_AUDIT:cell hook-codex -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/hook-codex.sh` (`tmux attach -t audit-hook-codex`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell hook-codex -->

### mcp × claude [PASS]

<!-- BEGIN_AUDIT:cell mcp-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/mcp-claude.sh` (`tmux attach -t audit-mcp-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell mcp-claude -->

### mcp × codex [PASS]

<!-- BEGIN_AUDIT:cell mcp-codex -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/mcp-codex.sh` (`tmux attach -t audit-mcp-codex`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell mcp-codex -->

### mcp × gemini [FAIL]

<!-- BEGIN_AUDIT:cell mcp-gemini -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/mcp-gemini.sh` (`tmux attach -t audit-mcp-gemini`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell mcp-gemini -->

### mcp × opencode [PASS]

<!-- BEGIN_AUDIT:cell mcp-opencode -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/mcp-opencode.sh` (`tmux attach -t audit-mcp-opencode`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell mcp-opencode -->

### pi-extension × pi [PASS]

<!-- BEGIN_AUDIT:cell pi-extension-pi -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/pi-extension-pi.sh` (`tmux attach -t audit-pi-extension-pi`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell pi-extension-pi -->

### plugin × claude [PASS]

<!-- BEGIN_AUDIT:cell plugin-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/plugin-claude.sh` (`tmux attach -t audit-plugin-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell plugin-claude -->

### skill × claude [PASS]

<!-- BEGIN_AUDIT:cell skill-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-claude.sh` (`tmux attach -t audit-skill-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-claude -->

### skill × codex [PASS]

<!-- BEGIN_AUDIT:cell skill-codex -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-codex.sh` (`tmux attach -t audit-skill-codex`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-codex -->

### skill × gemini [FAIL]

<!-- BEGIN_AUDIT:cell skill-gemini -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-gemini.sh` (`tmux attach -t audit-skill-gemini`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-gemini -->

### skill × opencode [PASS]

<!-- BEGIN_AUDIT:cell skill-opencode -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-opencode.sh` (`tmux attach -t audit-skill-opencode`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-opencode -->

### skill × pi [PASS]

<!-- BEGIN_AUDIT:cell skill-pi -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-pi.sh` (`tmux attach -t audit-skill-pi`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-pi -->

