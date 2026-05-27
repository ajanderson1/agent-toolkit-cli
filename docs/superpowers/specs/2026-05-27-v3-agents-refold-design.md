# v3.0.0 — Agents Refold (design spec)

**Date:** 2026-05-27
**Status:** approved (brainstorm) → ready for research dispatch
**Scope:** Reintroduce the `agent` (subagent-definition) asset kind, stripped out after v1.

---

## Terminology (read first)

The word "agent" is overloaded in this codebase. This spec uses:

- **harness** — one of the ~54 AI coding tools the toolkit projects assets into
  (Claude Code, Cursor, Codex, Gemini CLI, Pi, …). The catalog in
  `src/agent_toolkit_cli/skill_agents.py` confusingly calls these "agents"
  because that is `vercel-labs/skills`'s term. When this spec says **harness**,
  it means that catalog entry.
- **agent** / **subagent** — a *deployable artifact*: a spawnable, separately
  defined assistant with its own instructions/tools (e.g. Claude Code's
  `.claude/agents/<slug>.md`). This is the **new asset kind** we are
  reintroducing — a sibling of `skill`. When this spec says **agent kind** or
  **subagent**, it means this artifact.

A subagent is NOT a skill, NOT a slash command, NOT an MCP server. The research
must hold this distinction firmly.

---

## Problem

v1 was a broad multi-kind asset toolkit. Its TUI had a left-hand `KindsSidebar`
offering `skill | agent | command | hook | plugin | mcp | pi-extension`, and its
`harness_adapters/` projected each kind into 5 harnesses (Claude, Codex,
OpenCode, Gemini, Pi). The "strip-back" reduced the tool to **skills-only**:
the sidebar is gone, `harness_adapters/` is empty, and the TUI is a single skill
grid.

v3.0.0 brings back **one** of those kinds — `agent` (subagents) — and the
left-hand selector that switches between kinds. The functionality must be
**compliant with all ~54 supported harnesses**: for every harness we must know
whether it has a subagent concept and, if so, exactly how it locates and calls
subagents.

## Goal

Ship v3.0.0 with the `agent` kind fully wired for every harness that genuinely
supports subagents, the `agent` column of a harness compatibility matrix
re-verified across all ~54 harnesses, and the left-hand kind selector restored
in the TUI. Everything else (command/hook/plugin/mcp/pi-extension) stays out of
scope.

## Non-goals (v3.0.0)

- Reintroducing `command`, `hook`, `plugin`, `mcp`, or `pi-extension` kinds.
  The sidebar MAY list them disabled/greyed, but only `agent` gets wired.
- Authoring subagent *content*. This is plumbing — projecting/installing
  subagent artifacts — not writing subagents.

---

## Two phases

This effort is **research-first**. The bridging artifact is the harness matrix;
everything downstream implements against it.

```
Phase A (research)  ──produces──▶  harness-matrix.md (agent row)  ──feeds──▶  Phase B (implementation plan)
```

### Phase A — Research (active now)

**Deliverable:** a refreshed `docs/agent-toolkit/harness-matrix.md` with a
complete, citation-grade `agent` row covering all ~54 harnesses, plus a GitHub
issue capturing the v3.0.0 epic with the matrix as its backbone.

**Method:** winnow-then-deep-dive, batched by harness family, re-verifying ALL
54 (including v1's 5) against *current* upstream — v1's matrix data is ~3 weeks
old and harnesses move fast, so it is a prior to re-verify, not trusted.

**Per-harness two-stage protocol:**

1. **Winnow (fast triage, time-boxed):** Does this harness have any subagent
   concept distinct from skills/commands/MCPs? → `yes` / `no` / `unknown`.
2. **Deep-dive (only `yes`/`unknown`):** capture the matrix cell:
   - **Mechanism:** `symlink` / `translate` / `config_file` / `dual-symlink` /
     `config_file+folder` (definitions in the matrix doc's "Mechanisms"
     section).
   - **User-scope target path** + **project-scope path**.
   - **File format** (markdown+frontmatter / TOML / JSON) and **required vs
     forbidden frontmatter fields** (e.g. Gemini's zod `.strict()` rejects extra
     top-level keys).
   - **Loader source citation:** file:line in current upstream repo, or doc URL
     — re-verified, not copied from v1.
   - **Verdict:** `supported` / `unsupported (gap)` / `unsupported (by design)`
     + one-line reasoning.

**Unknowns policy:** each harness gets a bounded search effort. If no subagent
evidence surfaces (dead project, no public docs/source), record
`unknown — no public evidence found` with a "what I checked" trail and move on.
Do not chase ghosts.

**Dispatch:** ~9 research agents, batched by likely shared lineage so each
exploits shared conventions. Indicative batches (membership finalized against
the live `skill_agents.py` list at dispatch time):

| Batch | Harnesses (indicative) |
|---|---|
| 1. Claude-lineage | claude-code, openclaw, kode, mux, command-code, codemaker |
| 2. Google/Gemini | gemini-cli, antigravity, qwen-code, iflow-cli |
| 3. OpenCode + forks | opencode, crush, goose |
| 4. Codex/OpenAI-likes | codex, kimi-cli, dexto |
| 5. Pi + agents-std | pi, amp, cline, warp, deepagents, firebender |
| 6. JetBrains/IDE | junie, qoder, trae, trae-cn, windsurf, cursor, continue, kilo, roo |
| 7. Enterprise/cloud | bob, codearts-agent, cortex, devin, droid, rovodev, tabnine-cli, zencoder |
| 8. China-market CLIs | codebuddy, codestudio, forgecode, hermes-agent, kiro-cli |
| 9. Long-tail | mcpjam, mistral-vibe, openhands, replit, github-copilot, neovate, pochi, adal |

**Output contract:** each agent returns a **matrix fragment** (the `agent`-row
cells for its batch, in the matrix-cell format above) plus its "what I checked"
trail. Agents do NOT write the doc directly — the orchestrator assembles all
fragments into the single refreshed `harness-matrix.md` to avoid 9 agents racing
on one file.

**v1 baseline to re-verify** (from `harness-matrix.md` at tag `v1.0.0`):

- **Claude:** `symlink → ~/.claude/agents/<slug>.md`.
- **Codex:** `translate → ~/.codex/agents/<slug>.toml`; TOML schema
  `name`/`description`/`developer_instructions` + `[agent_toolkit_cli]` table
  (#140).
- **OpenCode:** `translate → ~/.config/opencode/agents/<slug>.md`; inject
  `mode: subagent`, strip toolkit wrapper.
- **Gemini:** `translate → ~/.gemini/agents/<slug>.md`; **only** top-level
  `name`+`description` (zod `.strict()` rejects extras — wrapper omitted) (#97).
- **Pi:** `dual-symlink → ~/.pi/agent/agents/<slug>.md` AND `~/.agents/<slug>.md`
  via the `pi-subagents` extension; project scope mirrors `.pi/agents/` +
  `.agents/` (#75).

### Phase B — Implementation (separate plan, post-research)

Recorded here as direction only; gets its own `writing-plans` plan once the
matrix lands and the supported-harness set is known.

**Three reintroductions, each generalizing existing skills machinery to a
`kind` dimension (`skill` | `agent`):**

1. **`agent` projection adapters** — port/refresh v1's `harness_adapters/`
   (Claude symlink; Codex/OpenCode/Gemini translate; Pi dual-symlink), extended
   to every harness the matrix marks `supported`. The matrix is the contract:
   each `supported` cell = one adapter behavior. A parity test
   (`tests/test_harness_matrix.py` in v1) fails if doc and code disagree —
   reintroduce it.

2. **Install/lock/paths generalized to kinds** — `skill_install.py`,
   `skill_lock.py`, `skill_paths.py` are skill-hardcoded today. Teach them a
   `kind` dimension so subagents get the same canonical-clone +
   per-harness-projection + lockfile treatment. **Open design tension for the
   Phase B plan:** generalize in place (one set of `*_install.py` taking a
   `kind` arg) vs. parallel `agent_*` modules. Not decided here. Whichever wins,
   the lockfile schema gains a `kind` discriminator — if that change is
   non-back-compat with `vercel-labs/skills`'s lock readers, it is the v3.0.0
   (major) trigger.

3. **TUI `KindsSidebar`** — reintroduce v1's left-hand rail (`Skills` /
   `Agents`, per-kind counts, `1`/`2` hotkeys) driving the existing grid to
   re-render per selected kind. Other kinds stay defined-but-dormant.

**CLI surface (must mirror the full `skill` verb set).** The current `skill`
group exposes: `add`, `install`, `uninstall`, `remove`, `import`, `list`,
`status`, `update`, `push`, `reset` (+ `skill doctor`). v3.0.0 must provide the
equivalent for the `agent` kind. Two viable shapes — **decided in the Phase B
plan, not here:**

   - **(a) Parallel `agent` command group:** `agent-toolkit-cli agent add|install|
     uninstall|remove|import|list|status|update|push|reset`, mirroring `skill`.
   - **(b) `--kind` flag on the existing verbs:** `skill add --kind agent …`
     (or a renamed neutral group). Fewer commands, but muddies the `skill` name.

   Either way, **`agent import` is in scope**: it reconstructs an agent library
   from a lock file exactly as `skill import` does for skills (v2.12,
   `import_cmd.py` — `read_only=True`, monorepo parent-symlink reconstruction,
   `--latest`). The lock format's new `kind` discriminator must round-trip
   through import. `doctor` must also learn the `agent` kind (stray-symlink
   detection, orphan checks) — the matrix tells it which harness paths are
   legitimate agent slots.

**Explicitly out of scope for v3.0.0:** command/hook/plugin/mcp/pi-extension
adapters and CLI/TUI wiring. One kind per major version keeps the blast radius
sane.

---

## Success criteria

**Phase A done when:**
- `harness-matrix.md` has an `agent` row covering all ~54 harnesses, each cell a
  verdict (`supported` / `gap` / `by design` / `unknown`) with mechanism + path
  + format + current-upstream citation for every `supported` cell.
- A GitHub issue for the v3.0.0 epic exists, linking the matrix and listing the
  supported-harness set as the Phase B work surface.

**Phase B done when (defined fully in its own plan):**
- `agent` kind installs/projects correctly into every `supported` harness, with
  the parity test green.
- CLI exposes the full agent verb set incl. `agent import`; lock round-trips the
  `kind` discriminator.
- TUI `KindsSidebar` switches between `Skills` and `Agents`.

## Risks / open questions (for Phase B)

- **Lock schema compatibility:** does adding a `kind` discriminator break
  `vercel-labs/skills`'s lock readers? Determines whether v3.0.0's major bump is
  truly forced.
- **Generalize-in-place vs parallel modules:** the central Phase B architecture
  decision (`conventions` principle tension: simple defaults vs. avoiding
  duplication) — surface to user, do not silently pick.
- **CLI shape (a) vs (b):** parallel `agent` group vs `--kind` flag.
- **Long-tail unknowns:** harnesses that resolve to `unknown` ship as
  `unsupported (gap)` with a tracking issue, not blockers.
