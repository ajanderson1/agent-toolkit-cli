# Spec: expose Hermes as a main TUI harness

Issue: #469

## Problem

Hermes Agent is already present in the harness catalog and compatibility docs, but the Textual TUI's main-harness shortlist omits `hermes-agent`. Users can manage Hermes through catalog/CLI paths, yet the main interactive TUI does not represent Hermes alongside Claude, Gemini, Codex, OpenCode, Pi, and Cursor.

## Goal

Make Hermes part of the TUI's main-harness model for every asset type where Hermes has known support, without implying support for asset types that remain unsupported, unknown, or adapter-less.

## Current facts

- Catalog entry: `src/agent_toolkit_cli/skill_agents.py` has `hermes-agent` with:
  - project skills dir: `.hermes/skills`
  - global skills dir: `~/.hermes/skills`
  - no subagent file-drop mechanism
- Harness docs: `docs/harnesses/hermes-agent.md` says:
  - Instructions: native `AGENTS.md` reader
  - Skills: supported via `.hermes/skills`
  - Agents/subagents: unsupported by design
  - Commands: unknown
  - MCP servers: no toolkit adapter yet
  - Pi extensions: not applicable
- TUI composition: `src/agent_toolkit_tui/composition.py` centralizes `MAIN_HARNESSES` and derives per-asset rendered columns from support/coverage rules.

## Requirements

### R1 — Main-harness source of truth

`hermes-agent` is added to the TUI main-harness source of truth so all asset-type composition helpers evaluate Hermes consistently.

### R2 — Skills tab

Skills tab renders a dedicated `Hermes` column because Hermes uses `.hermes/skills`, not the shared `.agents/skills` Standard bucket.

Expected behavior:

- Per-skill Hermes cell probes the Hermes destination at current scope.
- Toggling Hermes queues `agent-toolkit-cli skill install/uninstall ... --agents hermes-agent` through existing apply flow.
- Project/global behavior mirrors other non-standard skill harnesses.

### R3 — Instructions tab

Instructions tab represents Hermes through existing native/Standard semantics because Hermes reads top-level `AGENTS.md` natively. This is the explicit product decision for this issue: under the current TUI design, a native no-toggle instructions reader is exposed through the Standard/native column rather than through a duplicate dedicated column.

Expected behavior:

- No Hermes pointer/toggle column is added for instructions.
- Standard/native count and info include Hermes wherever native readers are enumerated.
- Automated tests prove Hermes is covered by native/Standard instructions handling, so there is a concrete visible/explainable Hermes surface even without a per-harness toggle.
- A future dedicated read-only native column would require a separate issue because it changes the Standard-column policy for all native instructions readers, not only Hermes.

### R4 — Non-applicable asset types stay honest

Do not expose Hermes as an actionable TUI column for unsupported/unknown/no-adapter asset types.

- Agents/subagents: no Hermes column; Hermes delegation is runtime-only and has no file-drop agent directory.
- Commands: no Hermes column until command support is evidenced and adapter-backed.
- MCP servers: no Hermes column until an MCP adapter exists.
- Pi extensions: unchanged; Pi-only.

### R5 — Display name

TUI labels render Hermes as `Hermes` rather than `Hermes-agent` or raw `hermes-agent`.

### R6 — Regression protection

Tests cover:

- `MAIN_HARNESSES` includes `hermes-agent` in canonical order.
- Skills composition includes `hermes-agent` as a non-standard main harness.
- Instructions composition keeps Hermes covered by native/Standard behavior.
- Agents/commands/MCP/pi-extension surfaces do not gain unsupported Hermes toggles.
- Existing main harness coverage still passes.

## Non-goals

- Add new Hermes asset-type adapters.
- Change Hermes compatibility verdicts without new evidence.
- Redesign the TUI Standard-column model.
- Add long-tail harness display back to the TUI.

## Open decisions

None. Implementation should preserve current Standard-column model unless tests reveal it cannot represent Hermes clearly.
